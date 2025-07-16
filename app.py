import os
import logging
import threading
import time
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for
from airtable import Airtable
from collections import defaultdict

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- Configuration ---
AIRTABLE_API_KEY = os.environ.get('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.environ.get('AIRTABLE_BASE_ID')

# Table names
TABLES = {
    'influencers': 'influencerTable',
    'posts': 'postTable',
    'errors': 'contentErrorLogTable',
    'campaigns': 'campaignTable'
}

# --- Initialize Airtable Connections ---
app.logger.info("Initializing Airtable connections...")
tables = {}
active_campaigns = {}

if AIRTABLE_API_KEY and AIRTABLE_BASE_ID:
    try:
        for name, table_id in TABLES.items():
            tables[name] = Airtable(AIRTABLE_BASE_ID, table_id, AIRTABLE_API_KEY)

        # Test connection
        tables['influencers'].get_all(max_records=1)
        app.logger.info("Airtable connection successful")
    except Exception as e:
        app.logger.error(f"Airtable connection failed: {str(e)}")
else:
    app.logger.error("Missing AIRTABLE_API_KEY or AIRTABLE_BASE_ID in environment")

# --- Helper Functions ---
def get_record(table_name, record_id, default=None):
    """Generic function to get a record from any table"""
    if not record_id or table_name not in tables:
        return default
    try:
        return tables[table_name].get(record_id)
    except Exception:
        return default

def get_influencer_name(influencer_id):
    """Get influencer name by ID"""
    record = get_record('influencers', influencer_id)
    return record['fields'].get('Name', 'Unknown Influencer') if record else 'Unknown Influencer'

def get_campaign_details(campaign_id):
    """Get campaign details by ID"""
    record = get_record('campaigns', campaign_id)
    return record['fields'] if record else None

def ensure_list(value):
    """Ensure the value is a list"""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]

def get_campaign_value(campaign_record_id):
    """Get campaign value from record ID"""
    campaign = get_record('campaigns', campaign_record_id)
    if not campaign:
        return campaign_record_id

    fields = campaign.get('fields', {})
    for field_name in ['CampaignID', 'ID', 'Campaign_ID', 'campaign_id', 'campaignId']:
        if field_name in fields:
            value = fields[field_name]
            return str(value) if isinstance(value, (int, float)) else value

    return campaign_record_id

def get_first_name(full_name):
    """Extract first name from 'Surname, First Name' format"""
    if not full_name:
        return "Unknown"

    if ',' in full_name:
        parts = full_name.split(',', 1)
        return parts[0].strip() if len(parts) > 1 else parts[0].strip()
    return full_name.strip()

def get_campaign_name_from_value(campaign_value):
    """Get campaign name from campaign value (not record ID)"""
    if not campaign_value:
        return "No Campaign Selected"

    try:
        # Search for campaign by value in different fields
        for field_name in ['CampaignID', 'ID', 'Campaign_ID', 'campaign_id', 'campaignId']:
            formula = f"{{{field_name}}}='{campaign_value}'"
            try:
                campaigns = tables['campaigns'].get_all(formula=formula)
                if campaigns:
                    campaign = campaigns[0]  # Get the first match
                    fields = campaign.get('fields', {})
                    for name_field in ['campaignName', 'name', 'Name', 'campaign_name', 'CampaignName']:
                        if name_field in fields and fields[name_field]:
                            return fields[name_field]
            except Exception:
                continue

        # If not found by formula, return the value
        return f"Campaign {campaign_value}"

    except Exception as e:
        app.logger.error(f"Error getting campaign name from value {campaign_value}: {str(e)}")
        return f"Campaign {campaign_value}"

def debug_campaign_data(campaign_id):
    """Debug function to see what's in the campaign record"""
    try:
        campaign_record = get_record('campaigns', campaign_id)
        if campaign_record:
            print(f"Campaign record for ID {campaign_id}:")
            print(f"Full record: {campaign_record}")
            print(f"Fields: {campaign_record.get('fields', {})}")

            # Check what fields are available
            fields = campaign_record.get('fields', {})
            print(f"Available field names: {list(fields.keys())}")

            # Try to find name fields
            for field_name in fields.keys():
                if 'name' in field_name.lower() or 'campaign' in field_name.lower():
                    print(f"Potential name field: {field_name} = {fields[field_name]}")
        else:
            print(f"No campaign record found for ID: {campaign_id}")

        # Also check all campaigns to see the structure
        print("\nAll campaigns structure:")
        all_campaigns = tables['campaigns'].get_all(max_records=3)
        for i, campaign in enumerate(all_campaigns):
            print(f"Campaign {i}: {campaign.get('fields', {})}")

    except Exception as e:
        print(f"Error debugging campaign data: {str(e)}")

def get_campaign_name(campaign_id):
    """Get formatted campaign name with better error handling"""
    if not campaign_id:
        return "No Campaign Selected"

    try:
        # Try to get the campaign record
        campaign_record = get_record('campaigns', campaign_id)

        if campaign_record and 'fields' in campaign_record:
            # Try different possible field names for campaign name
            fields = campaign_record['fields']
            for field_name in ['campaignName', 'name', 'Name', 'campaign_name', 'CampaignName']:
                if field_name in fields and fields[field_name]:
                    return fields[field_name]

        # If no campaign name found, return the ID
        return f"Campaign {campaign_id}"

    except Exception as e:
        app.logger.error(f"Error getting campaign name for ID {campaign_id}: {str(e)}")
        return f"Campaign {campaign_id}"

# --- Data Processing Functions ---
def parse_error_description(error_desc):
    """Parse error description and extract unique hashtags and tags"""
    missing_hashtags = set()
    missing_tags = set()

    for part in error_desc.split("Partially Correct/Incorrect"):
        if not part.strip():
            continue

        for error_part in part.split("-"):
            error_part = error_part.strip()
            if error_part.startswith("Missing Hashtags:"):
                hashtags = [h.strip() for h in error_part.replace("Missing Hashtags:", "").split(",") if h.strip()]
                missing_hashtags.update(hashtags)
            elif error_part.startswith("Missing Tags:"):
                tags = [t.strip() for t in error_part.replace("Missing Tags:", "").split(",") if t.strip()]
                missing_tags.update(tags)

    return list(missing_hashtags), list(missing_tags)

def format_suggested_message(first_name, campaign_name, error_parts=None, flag=None, post_link=None):
    """Format the suggested message with feedback option"""
    if flag == 'Take Down Video':
        message_lines = [
            f"Hi {first_name},",
            f"We are issuing a takedown notice for your recent post for {campaign_name or 'the campaign'}:",
            *(error_parts or []),
            f"View it here: {post_link or 'your post'}",
            "Please take it down promptly.",
            "Thanks!"
        ]
    elif flag == 'Video Ok':
        message_lines = [
            f"Hi {first_name},",
            f"We are confirming that your recent post for {campaign_name or 'the campaign'} is approved:",
            f"View it here: {post_link or 'your post'}",
            "It can remain online.",
            "Thanks!"
        ]
    elif error_parts:
        message_lines = [
            f"Hi {first_name},",
            f"We noticed issues with your recent post for {campaign_name or 'the campaign'}:",
            *error_parts,
            f"View it here: {post_link or 'your post'}",
            "Please review and update.",
            "Thanks!"
        ]
    else:
        message_lines = [
            f"Hi {first_name},",
            f"Great job on your recent post for {campaign_name or 'the campaign'}!",
            f"View it here: {post_link or 'your post'}",
            "Your content looks perfect and meets all requirements.",
            "Thank you for your excellent work!",
            "Keep it up!"
        ]
    return "\n".join(message_lines)

def get_active_influencers():
    """Get active influencers with their TikTok links"""
    formula = "AND({Active}='YES')" #, {Audited}='YES'
    try:
        records = tables['influencers'].get_all(formula=formula)
        return {rec['fields'].get('TiktokLink', '').strip(): rec for rec in records if rec['fields'].get('TiktokLink')}
    except Exception as e:
        app.logger.error(f"Error getting active influencers: {str(e)}")
        return {}

def get_campaign_posts(campaign_value):
    """Get posts for a specific campaign"""
    try:
        if campaign_value:
            formula = f"{{CampaignId}}='{campaign_value}'"
            return tables['posts'].get_all(formula=formula)
        return tables['posts'].get_all()
    except Exception as e:
        app.logger.error(f"Error getting campaign posts: {str(e)}")
        return []

# --- Core Business Logic ---
def trigger_n8n_audit(campaign_id):
    """Background task to trigger n8n audit"""
    script_url = "https://script.google.com/macros/s/AKfycbzRsWR8IfOAacu208nin_dlqTLLDRBZXhuVx6yUQ_BjsPrV6MVnlkZontzcWBPkjG4/exec"
    campaign_name = get_campaign_name(campaign_id)

    try:
        app.logger.info(f"Triggering n8n for campaign: {campaign_name}")
        response = requests.post(script_url, json={'campaign_name': campaign_name}, timeout=30)

        if response.status_code == 200:
            app.logger.info(f"Audit triggered for {campaign_name}")
        else:
            app.logger.error(f"Proxy error: {response.status_code} - {response.text}")
    except Exception as e:
        app.logger.error(f"Error triggering audit: {str(e)}")
    finally:
        time.sleep(10)
        active_campaigns.pop(campaign_id, None)

def compute_summary_data(campaign_id):
    """Compute summary data for a campaign"""
    try:
        campaign_value = get_campaign_value(campaign_id) if campaign_id else None

        # Get active influencers
        active_influencers = get_active_influencers()
        active_tiktok_links = set(active_influencers.keys())

        # Get campaign posts
        campaign_posts = get_campaign_posts(campaign_value)

        # Initialize counters
        posts_with_issues = 0
        posts_no_issues = 0
        posted_tiktok_links = set()
        posts_for_manual_review = 0

        # Process posts
        for post in campaign_posts:
            fields = post.get('fields', {})
            tiktok_link = fields.get('TikTokLink', '').strip()
            post_flag = fields.get('ManualFlag')  # This is the field we check for manual review

            if tiktok_link:
                posted_tiktok_links.add(tiktok_link)

            quality = fields.get('PostQuality', '').strip()
            if quality == 'All Correct':
                posts_no_issues += 1
            elif quality == 'Partially Correct/Incorrect':
                posts_with_issues += 1

            # Count posts with no "ManualFlag" value as needing manual review
            if not post_flag:
                posts_for_manual_review += 1

        # Calculate metrics
        total_influencers = len(active_influencers)
        videos_not_loaded = len(active_tiktok_links - posted_tiktok_links)

        return {
            "number_of_influencers": total_influencers,
            "videos_with_no_issues": posts_no_issues,
            "videos_with_issues": posts_with_issues,
            "videos_not_loaded_yet": videos_not_loaded,
            "videos_for_manual_review": posts_for_manual_review,
        }

    except Exception as e:
        app.logger.error(f"Error computing summary data: {str(e)}")
        return {
            "number_of_influencers": 0,
            "videos_with_no_issues": 0,
            "videos_with_issues": 0,
            "videos_not_loaded_yet": 0,
            "videos_for_manual_review": 0,
        }

def get_all_posts_without_issues(campaign_value):
    """Get all posts without issues for the campaign"""
    try:
        # Get all posts for the campaign
        posts = get_campaign_posts(campaign_value)

        # Get posts with issues to exclude them
        posts_with_issues = get_all_posts_with_issues(campaign_value)
        issue_post_ids = {post['postId'] for post in posts_with_issues} if posts_with_issues else set()
        influencers = tables['influencers'].get_all()
        contact_map = {}
        for inf in influencers:
            name = inf['fields'].get('Name')
            if name:
                contact_map[name] = inf['fields'].get('ContactNumber', '')

        results = []

        # Get campaign name once for all posts
        campaign_name = get_campaign_name_from_value(campaign_value)

        for post in posts:
            post_id = post['id']
            fields = post.get('fields', {})
            post_link = fields.get('PostLink', '')


            # Skip posts that have issues
            if post_id in issue_post_ids:
                continue

            # Only include posts with "All Correct" quality
            quality = fields.get('PostQuality', '').strip()
            if quality != 'All Correct' or not post_link:
                continue

            # Process influencer name
            full_name = fields.get('InfluencerName', 'Unknown Influencer')
            first_name = get_first_name(full_name)
            contact_number = str(contact_map.get(full_name, ''))

            suggested_message = format_suggested_message(first_name, campaign_name)

            results.append({
                'postId': post_id,
                'influencerName': full_name,
                'videoLink': post_link,
                'issueCaption': None,
                'suggestedMessage': suggested_message,
                'hasIssues': False,
                'currentRating': fields.get('manualRating', 0),
                'currentFlag': fields.get('reviewFlag', ''),
                'contactNumber': contact_number or '',
                'type': 'combined'
            })

        return results
    except Exception as e:
        app.logger.error(f"Error getting posts without issues: {str(e)}")
        return []

def get_all_posts_with_issues(campaign_value):
    """Get all posts with issues for the campaign"""
    try:
        # Group errors by post ID
        all_errors = defaultdict(list)
        for error in tables['errors'].get_all():
            error_fields = error.get('fields', {})
            for pid in ensure_list(error_fields.get('postId', [])):
                all_errors[str(pid)].append(error_fields.get('errorDescription', 'Unknown error'))

        # Get all posts for the campaign
        posts = get_campaign_posts(campaign_value)

        influencers = tables['influencers'].get_all()
        contact_map = {}
        for inf in influencers:
            name = inf['fields'].get('Name')
            if name:
                contact_map[name] = inf['fields'].get('ContactNumber', '')

        # Create post ID mapping
        post_id_to_record = {}
        for post in posts:
            fields = post.get('fields', {})
            for field in ['PostID', 'ID', 'Post_ID', 'post_id', 'postId', 'id']:
                if field in fields and fields[field]:
                    post_id_to_record[str(fields[field])] = post
                    break

        results = []
        processed_links = set()

        # Get campaign name once for all posts
        campaign_name = get_campaign_name_from_value(campaign_value)

        for error_id, error_descriptions in all_errors.items():
            if error_id not in post_id_to_record:
                continue

            post = post_id_to_record[error_id]
            fields = post.get('fields', {})
            post_link = fields.get('PostLink', '')

            if post_link in processed_links:
                continue
            processed_links.add(post_link)

            # Process influencer name
            full_name = fields.get('InfluencerName', 'Unknown Influencer')
            first_name = get_first_name(full_name)
            contact_number = str(contact_map.get(full_name, ''))

            # Process errors
            all_hashtags = set()
            all_tags = set()
            for desc in error_descriptions:
                hashtags, tags = parse_error_description(desc)
                all_hashtags.update(hashtags)
                all_tags.update(tags)

            # Format message
            error_parts = []
            if all_hashtags:
                error_parts.append(f"Missing Hashtags: {', '.join(sorted(all_hashtags))}")
            if all_tags:
                error_parts.append(f"Missing Tags: {', '.join(sorted(all_tags))}")

            suggested_message = format_suggested_message(
                first_name,
                campaign_name,
                error_parts
            )

            results.append({
                'postId': post['id'],
                'influencerName': full_name,
                'videoLink': post_link or '#',
                'issueCaption': "; ".join(error_parts) or "Please review your post",
                'suggestedMessage': suggested_message,
                'hasIssues': True,
                'currentRating': fields.get('manualRating', 0),
                'currentFlag': fields.get('reviewFlag', ''),
                'contactNumber': contact_number or '',
                'type': 'combined'
            })

        return results
    except Exception as e:
        app.logger.error(f"Error getting posts with issues: {str(e)}")
        return []

def get_all_posts_combined(campaign_value):
    """Get all posts combined - issues first, then without issues"""
    campaign_name = get_campaign_name_from_value(campaign_value)
    posts_with_issues = get_all_posts_with_issues(campaign_value)
    posts_without_issues = get_all_posts_without_issues(campaign_value)

    # Combine with issues first
    combined = posts_with_issues + posts_without_issues

    # Add reviewed status and campaign name to each post
    for post in combined:
        post_record = get_record('posts', post.get('postId'))
        if post_record:
            fields = post_record.get('fields', {})
            post['reviewed'] = fields.get('reviewed', False)
            post['approved_Status'] = fields.get('approved_Status', 'NO')
        # Add campaign name to each post
        post['campaignName'] = campaign_name

    return combined

def process_not_uploaded_review(campaign_value, campaign_id):
    """Process influencers who haven't uploaded"""
    try:
        active_influencers = get_active_influencers()
        campaign_posts = get_campaign_posts(campaign_value)

        # Get posted links
        posted_links = set()
        for post in campaign_posts:
            fields = post.get('fields', {})
            tiktok_link = fields.get('TikTokLink', '').strip()
            if tiktok_link:
                posted_links.add(tiktok_link)

        # Prepare results
        results = []

        # Get campaign name - try from value first, then from record ID
        campaign_name = get_campaign_name_from_value(campaign_value)
        if campaign_name.startswith('Campaign ') or not campaign_name:
            # If we couldn't find it by value, try by record ID
            campaign_name = get_campaign_name(campaign_id)

        for tiktok_link, influencer in active_influencers.items():
            if tiktok_link in posted_links:
                continue

            fields = influencer['fields']
            full_name = fields.get('Name', 'Unknown Influencer')
            first_name = get_first_name(full_name)
            contact_number = str(fields.get('ContactNumber', ''))

            results.append({
                'influencerId': influencer['id'],
                'influencerName': full_name,
                'tiktokLink': tiktok_link,
                'instagramLink': fields.get('InstagramLink', '#'),
                'suggestedMessage': (
                    f"Hi {first_name},\n"
                    f"We noticed you haven't uploaded your video for {campaign_name} yet.\n"
                    "Please upload it as soon as possible.\n"
                    "Thanks!"
                ),
                'contactNumber': contact_number or '',
                'type': 'not_uploaded'
            })

        return results
    except Exception as e:
        app.logger.error(f"Error processing not uploaded: {str(e)}")
        return []

def process_manual_review(campaign_value):
    """Process posts needing manual review"""
    try:
        formula = f"{{PostQuality}}='Manual Review' AND {{CampaignId}}='{campaign_value}'" if campaign_value else "{PostQuality}='Manual Review'"
        posts = tables['posts'].get_all(formula=formula)

        return [{
            'postId': post['id'],
            'influencerName': post['fields'].get('InfluencerName', 'Unknown Influencer'),
            'videoLink': post['fields'].get('PostLink', '#'),
            'transcript': post['fields'].get('VideoTranscription', 'No transcript available'),
            'currentFlag': post['fields'].get('reviewFlag', ''),
            'type': 'manual_review'
        } for post in posts]
    except Exception as e:
        app.logger.error(f"Error processing manual review: {str(e)}")
        return []



# --- New Routes ---
@app.route('/save_flag', methods=['POST'])
def save_flag():
    """Save review flag to Airtable"""
    try:
        data = request.json
        post_id = data.get('postId')
        flag = data.get('flag')

        if not post_id or not flag:
            return jsonify({"error": "Missing postId or flag"}), 400

        # Update the post record in Airtable
        tables['posts'].update(post_id, {'ManualFlag': flag})

        app.logger.info(f"Flag saved: Post {post_id} flagged as {flag}")
        return jsonify({"status": "success", "message": "Flag saved successfully"})
    except Exception as e:
        app.logger.error(f"Flag error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/save_rating', methods=['POST'])
def save_rating():
    """Save rating to Airtable"""
    try:
        data = request.json
        post_id = data.get('postId')
        rating = data.get('rating')

        if not post_id or not rating:
            return jsonify({"error": "Missing postId or rating"}), 400

        # Validate rating
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({"error": "Rating must be between 1 and 5"}), 400

        # Update the post record in Airtable
        tables['posts'].update(post_id, {'manualRating': rating})

        app.logger.info(f"Rating saved: Post {post_id} rated {rating}")
        return jsonify({"status": "success", "message": "Rating saved successfully"})
    except Exception as e:
        app.logger.error(f"Rating error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/log_message', methods=['POST'])
def log_message():
    """Log message sending activity"""
    try:
        data = request.json
        app.logger.info(
            f"Message sent to {data.get('contactNumber')} "
            f"for {data.get('influencerName')}: "
            f"{data.get('message')}"
        )
        return jsonify({"status": "success"}), 200
    except Exception as e:
        app.logger.error(f"Log error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Existing Routes ---
@app.route('/')
def root():
    return redirect(url_for('campaign_select'))

@app.route('/summary')
def summary_page():
    """Show summary page for a campaign"""
    campaign_id = request.args.get('campaign_id', '')
    campaign_name = get_campaign_name(campaign_id) if campaign_id else ""

    if not tables:
        return "Airtable connection error", 500

    try:
        summary_data = compute_summary_data(campaign_id)
        return render_template(
            'index.html',
            summary_data=summary_data,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            active_campaigns=active_campaigns
        )
    except Exception as e:
        app.logger.error(f"Summary error: {str(e)}")
        return f"Server Error: {str(e)}", 500

@app.route('/campaign_select')
def campaign_select():
    """Campaign selection screen"""
    if 'campaigns' not in tables:
        return "Airtable connection error", 500

    try:
        campaigns = tables['campaigns'].get_all()
        campaign_list = [{
            'id': c['id'],
            'name': c['fields'].get('campaignName', 'Unnamed Campaign')
        } for c in campaigns]

        return render_template('campaign_select.html', campaigns=campaign_list)
    except Exception as e:
        app.logger.error(f"Campaign select error: {str(e)}")
        return "Error loading campaigns", 500

@app.route('/mark_reviewed', methods=['POST'])
def mark_reviewed():
    """Mark post as reviewed"""
    try:
        data = request.json
        post_id = data.get('postId')
        reviewed = data.get('reviewed')  # True or False

        if not post_id:
            return jsonify({"error": "Missing postId"}), 400

        tables['posts'].update(post_id, {'reviewed': reviewed})
        app.logger.info(f"Review status saved: Post {post_id} - {reviewed}")
        return jsonify({"status": "success", "message": "Review status saved"})
    except Exception as e:
        app.logger.error(f"Review status error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/approve_post', methods=['POST'])
def approve_post():
    """Set approval status for a post"""
    try:
        data = request.json
        post_id = data.get('postId')
        status = data.get('status')  # 'YES' or 'NO'

        if not post_id or not status:
            return jsonify({"error": "Missing postId or status"}), 400

        tables['posts'].update(post_id, {'approved_Status': status})
        app.logger.info(f"Approval status saved: Post {post_id} - {status}")
        return jsonify({"status": "success", "message": "Approval status saved"})
    except Exception as e:
        app.logger.error(f"Approval error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/start_audit', methods=['POST'])
def start_audit():
    """Start audit process for a campaign"""
    campaign_id = request.json.get('campaign_id')
    if not campaign_id:
        return jsonify({'error': 'Missing campaign_id'}), 400

    campaign_name = get_campaign_name(campaign_id)
    thread = threading.Thread(target=trigger_n8n_audit, args=(campaign_id,))
    thread.daemon = True
    thread.start()

    active_campaigns[campaign_id] = True
    return jsonify({
        "status": "success",
        "message": f"Audit started for campaign: {campaign_name}",
        "redirect_url": url_for('summary_page', campaign_id=campaign_id)
    })

@app.route('/audit_status')
def audit_status():
    return jsonify({'active_audits': list(active_campaigns.keys())})

@app.route('/get_review_data')
def get_review_data():
    """Endpoint for review data"""
    review_type = request.args.get('type')
    campaign_id = request.args.get('campaign_id', '')

    # Safely get campaign_value
    try:
        campaign_value = get_campaign_value(campaign_id) if campaign_id else ''
    except Exception as e:
        app.logger.error(f"Error getting campaign value: {str(e)}")
        campaign_value = ''

    if not tables:
        return jsonify({'error': 'Airtable connection failed'}), 500

    try:
        if review_type == 'combined':
            results = get_all_posts_combined(campaign_value)
        elif review_type == 'issues':
            results = get_all_posts_with_issues(campaign_value)
        elif review_type == 'not_uploaded':
            results = process_not_uploaded_review(campaign_value, campaign_id)
        elif review_type == 'manual_review':
            results = process_manual_review(campaign_value)
        else:
            return jsonify({'error': 'Invalid review type'}), 400

        return jsonify(results)
    except Exception as e:
        app.logger.error(f"Review data error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_summary_data')
def get_summary_data():
    """Endpoint for summary data"""
    campaign_id = request.args.get('campaign_id', '')
    try:
        summary_data = compute_summary_data(campaign_id)
        return jsonify(summary_data)
    except Exception as e:
        app.logger.error(f"Summary data error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/send_message', methods=['POST'])
def send_message():
    """Handle message sending with contact number"""
    try:
        data = request.json
        post_id = data.get('postId')
        message = data.get('message')
        contact_number = data.get('contactNumber', '')  # Get contact number

        if not post_id or not message:
            app.logger.info("Message did not send")
            return jsonify({"error": "Missing data"}), 400

        # Log message with contact number
        app.logger.info(
            f"Message sent for post {post_id} to {contact_number}: {message}"
        )

        return jsonify({
            "status": "success",
            "message": "Message sent",
            "contactNumber": contact_number or '' # Optional: return in response
        })
    except Exception as e:
        app.logger.error(f"Message error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/save_comment', methods=['POST'])
def save_comment():
    """Save comments"""
    try:
        data = request.json
        post_id = data.get('postId')
        comment = data.get('comment')

        if not post_id or not comment:
            return jsonify({"error": "Missing data"}), 400

        # Update the post record in Airtable
        tables['posts'].update(post_id, {'managerComment': comment})

        app.logger.info(f"Comment saved for post {post_id}: {comment}")
        return jsonify({"status": "success", "message": "Comment saved"})
    except Exception as e:
        app.logger.error(f"Comment error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
