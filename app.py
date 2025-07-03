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

# Table names from your structure
INFLUENCERS_TABLE = 'influencerTable'
POSTS_TABLE = 'postTable'
ERRORS_TABLE = 'contentErrorLogTable'
CAMPAIGNS_TABLE = 'campaignTable'

# --- Initialize Airtable Connections ---
app.logger.info("Initializing Airtable connections...")
influencers_table = None
posts_table = None
errors_table = None
campaigns_table = None
active_campaigns = {}  # Track campaigns being audited

if AIRTABLE_API_KEY and AIRTABLE_BASE_ID:
    try:
        influencers_table = Airtable(AIRTABLE_BASE_ID, INFLUENCERS_TABLE, AIRTABLE_API_KEY)
        posts_table = Airtable(AIRTABLE_BASE_ID, POSTS_TABLE, AIRTABLE_API_KEY)
        errors_table = Airtable(AIRTABLE_BASE_ID, ERRORS_TABLE, AIRTABLE_API_KEY)
        campaigns_table = Airtable(AIRTABLE_BASE_ID, CAMPAIGNS_TABLE, AIRTABLE_API_KEY)

        # Test connection
        influencers_table.get_all(max_records=1)
        app.logger.info("Airtable connection successful")
    except Exception as e:
        app.logger.error(f"Airtable connection failed: {str(e)}")
else:
    app.logger.error("Missing AIRTABLE_API_KEY or AIRTABLE_BASE_ID in environment")

# --- Helper Functions ---
def get_influencer_name(influencer_id):
    """Get influencer name by ID"""
    if not influencer_id or not influencers_table:
        return "Unknown Influencer"
    try:
        record = influencers_table.get(influencer_id)
        return record['fields'].get('Name', 'Unknown Influencer')
    except:
        return "Unknown Influencer"

def get_influencer_details(influencer_id):
    """Get influencer details by ID"""
    if not influencer_id or not influencers_table:
        return None
    try:
        return influencers_table.get(influencer_id)['fields']
    except:
        return None

def get_campaign_details(campaign_id):
    """Get campaign details by ID"""
    if not campaign_id or not campaigns_table:
        return None
    try:
        return campaigns_table.get(campaign_id)['fields']
    except:
        return None

def ensure_list(value):
    """Ensure the value is a list, even if it's a single value"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]

def get_required_tags(campaign_id):
    """Get required tags and hashtags for a campaign"""
    campaign = get_campaign_details(campaign_id)
    if not campaign:
        return "", ""
    hashtags = campaign.get('requiredHastags', '')
    tags = campaign.get('requiredTags', '')
    return hashtags, tags

def get_campaign_name(campaign_id):
    """Get name of campaign"""
    campaign = get_campaign_details(campaign_id)
    if not campaign:
        return "", ""
    campaign_name = campaign.get('campaignName', '')
    app.logger.info(f"Triggering n8n via Google Apps Script for campaign {campaign_name}")
    return campaign_name

def get_campaign_value(campaign_record_id):
    if not campaign_record_id or not campaigns_table:
        return None
    try:
        campaign_record = campaigns_table.get(campaign_record_id)
        fields = campaign_record.get('fields', {})

        # Try different field names
        for field_name in ['CampaignID', 'ID', 'Campaign_ID', 'campaign_id', 'campaignId']:
            if field_name in fields:
                value = fields[field_name]
                # Convert to string if it's a number
                return str(value) if isinstance(value, (int, float)) else value

        # Fallback to record ID
        return campaign_record_id
    except Exception as e:
        app.logger.error(f"Error getting campaign value: {str(e)}")
        return None

def trigger_n8n_audit(campaign_id):
    """Background task to trigger n8n audit"""
    script_url = "https://script.google.com/macros/s/AKfycbzRsWR8IfOAacu208nin_dlqTLLDRBZXhuVx6yUQ_BjsPrV6MVnlkZontzcWBPkjG4/exec"
    campaign_name = ""
    try:
        campaign_details = get_campaign_details(campaign_id)
        if campaign_details:
            campaign_name = campaign_details.get('campaignName', 'Unnamed Campaign')
        else:
            campaign_name = f"Campaign {campaign_id}"
    except Exception as e:
        app.logger.error(f"Error getting campaign name: {str(e)}")
        campaign_name = f"Campaign {campaign_id}"
    try:
        app.logger.info(f"Triggering n8n via Google Apps Script for campaign: {campaign_name}")
        response = requests.post(
            script_url,
            json={'campaign_name': campaign_name},
            timeout=30
        )
        if response.status_code == 200:
            app.logger.info(f"n8n audit triggered successfully for campaign: {campaign_name}")
            app.logger.debug(f"Proxy response: {response.text}")
        else:
            app.logger.error(f"Proxy error: {response.status_code} - {response.text}")
    except Exception as e:
        app.logger.error(f"Error triggering n8n audit via proxy: {str(e)}")
    finally:
        time.sleep(10)
        active_campaigns.pop(campaign_id, None)

# --- Routes ---
@app.route('/')
def root():
    """Redirect to campaign selection page"""
    return redirect(url_for('campaign_select'))


@app.route('/summary')
def summary_page():
    """Show summary page for a specific campaign"""
    campaign_id = request.args.get('campaign_id', '')
    campaign_name = ""
    if campaign_id:
        campaign = get_campaign_details(campaign_id)
        if campaign:
            campaign_name = campaign.get('campaignName', campaign_id)
        else:
            campaign_name = campaign_id
    if not all([posts_table, influencers_table, errors_table]):
        return "Airtable connection error. Check server logs.", 500
    try:
        all_posts = posts_table.get_all()
        all_influencers = influencers_table.get_all()
        all_errors = errors_table.get_all()

        # Get active influencers using profile links
        active_influencers = set()
        for influencer in all_influencers:
            fields = influencer.get('fields', {})
            if fields.get('Active', '').upper() == 'YES':
                profile_link = fields.get('TiktokLink', '')
                if profile_link:
                    active_influencers.add(profile_link)

        # Use sets to track unique posts and avoid duplicates
        posts_with_issues_links = set()
        posts_no_issues = 0
        posts_for_manual_review = 0
        campaign_post_count = 0
        posted_profile_links = set()

        for post in all_posts:
            fields = post.get('fields', {})
            quality = fields.get('PostQuality', '').strip()
            post_campaign_id = fields.get('CampaignId', '')
            if campaign_id and post_campaign_id != campaign_id:
                continue

            campaign_post_count += 1

            # Track posted profile links
            post_tiktok_link = fields.get('TikTokLink', '')
            if post_tiktok_link:
                posted_profile_links.add(post_tiktok_link)

            # Get PostLink for deduplication
            post_link = fields.get('PostLink', '')

            # Categorize posts based on PostQuality
            if quality == 'All Correct':
                posts_no_issues += 1
            elif quality == 'Partially Correct/Incorrect':
                # Only count unique PostLinks to avoid duplicates
                if post_link:
                    posts_with_issues_links.add(post_link)
            # Add other quality conditions as needed

        # Calculate total active influencers
        total_influencers = len(active_influencers)

        # Calculate videos not loaded - start from 0 and increment
        videos_not_loaded = 0
        for active_influencer in active_influencers:
            if active_influencer not in posted_profile_links:
                videos_not_loaded += 1

        # Get actual count of posts with issues (deduplicated)
        posts_with_issues = len(posts_with_issues_links)

        summary_data = {
            "number_of_influencers": total_influencers,
            "videos_with_no_issues": posts_no_issues,
            "videos_with_issues": posts_with_issues,
            "videos_not_loaded_yet": videos_not_loaded,
            "videos_for_manual_review": posts_for_manual_review,
        }

        return render_template('index.html',
            summary_data=summary_data,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            active_campaigns=active_campaigns
        )
    except Exception as e:
        app.logger.error(f"Error in summary_page: {str(e)}")
        return f"Server Error: {str(e)}", 500

@app.route('/campaign_select')
def campaign_select():
    """Show campaign selection screen"""
    if not campaigns_table:
        return "Airtable connection error", 500
    try:
        campaigns = campaigns_table.get_all()
        campaign_list = []
        for c in campaigns:
            fields = c.get('fields', {})
            campaign_list.append({
                'id': c['id'],
                'name': fields.get('campaignName', 'Unnamed Campaign')
            })
        return render_template('campaign_select.html', campaigns=campaign_list)
    except Exception as e:
        app.logger.error(f"Error fetching campaigns: {str(e)}")
        return "Error loading campaigns", 500

@app.route('/start_audit', methods=['POST'])
def start_audit():
    """Start the audit process for a campaign"""
    campaign_id = request.json.get('campaign_id')
    if not campaign_id:
        return jsonify({'error': 'Missing campaign_id'}), 400
    campaign_name = ""
    try:
        campaign_details = get_campaign_details(campaign_id)
        if campaign_details:
            campaign_name = campaign_details.get('campaignName', campaign_id)
        else:
            campaign_name = campaign_id
    except:
        campaign_name = campaign_id
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
    """Check if any audits are active"""
    return jsonify({
        'active_audits': list(active_campaigns.keys())
    })


def get_first_name(full_name):
    """Extract first name from 'Surname, First Name' format"""
    if ',' in full_name:
        parts = full_name.split(',')
        if len(parts) >= 2:
            return parts[0].strip()
    return full_name.strip()

def parse_error_description(error_desc):
    """Parse error description and extract unique hashtags and tags"""
    missing_hashtags = set()
    missing_tags = set()

    # Split by "Partially Correct/Incorrect" to handle duplicates
    parts = error_desc.split("Partially Correct/Incorrect")

    for part in parts:
        if not part.strip():
            continue

        # Split by "-" to get different error types
        error_parts = part.split("-")

        for error_part in error_parts:
            error_part = error_part.strip()

            if error_part.startswith("Missing Hashtags:"):
                hashtags_str = error_part.replace("Missing Hashtags:", "").strip()
                # Split by comma and clean up
                hashtags = [h.strip() for h in hashtags_str.split(",") if h.strip()]
                missing_hashtags.update(hashtags)

            elif error_part.startswith("Missing Tags:"):
                tags_str = error_part.replace("Missing Tags:", "").strip()
                # Split by comma and clean up
                tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                missing_tags.update(tags)

    return list(missing_hashtags), list(missing_tags)


def format_suggested_message(first_name, campaign_name, error_parts):
    """Format the suggested message in a neater multi-line format"""
    message_lines = [f"Hi {first_name},"]
    message_lines.append(f"We noticed issues with your recent post for {campaign_name}:")

    # Add each error part on its own line
    for part in error_parts:
        message_lines.append(part)

    message_lines.append("Please review and update.")
    message_lines.append("Thanks!")

    return "\n".join(message_lines)

@app.route('/get_review_data')
def get_review_data():
    review_type = request.args.get('type')
    campaign_id = request.args.get('campaign_id', '')
    campaign_value = ''
    if campaign_id:
        try:
            campaign_record = campaigns_table.get(campaign_id)
            campaign_value = str(campaign_record.get('fields', {}).get('campaignId', ''))
        except Exception as e:
            app.logger.error(f"Could not get campaign value for record {campaign_id}: {e}")
            campaign_value = campaign_id

    if not all([posts_table, influencers_table, errors_table, campaigns_table]):
        return jsonify({'error': 'Airtable connection failed'}), 500

    try:
        if review_type == 'issues':
            # Group errors by post ID (field value, not record ID)
            all_errors = defaultdict(list)
            error_records = errors_table.get_all()

            app.logger.info(f"Found {len(error_records)} error records")

            for error in error_records:
                post_ids = ensure_list(error['fields'].get('postId', []))
                for pid in post_ids:
                    all_errors[str(pid)].append(error['fields'].get('errorDescription', 'Unknown error'))

            # Get all posts for the campaign
            formula = f"{{CampaignId}}='{campaign_value}'" if campaign_value else ""
            posts = posts_table.get_all(formula=formula)

            app.logger.info(f"Found {len(posts)} posts with formula: {formula}")

            # Create mapping from post ID field value to post record
            post_id_to_record = {}
            for post in posts:
                fields = post.get('fields', {})
                possible_fields = ['PostID', 'ID', 'Post_ID', 'post_id', 'postId', 'id']

                for field_name in possible_fields:
                    if field_name in fields and fields[field_name] is not None:
                        post_id_value = str(fields[field_name])
                        post_id_to_record[post_id_value] = post
                        break

            results = []
            processed_post_links = set()  # Track processed PostLinks to avoid duplicates

            # Match errors to posts using the mapping
            for error_post_id, error_descriptions in all_errors.items():
                if error_post_id in post_id_to_record:
                    post = post_id_to_record[error_post_id]
                    fields = post.get('fields', {})

                    # Check for duplicate PostLink
                    post_link = fields.get('PostLink', '')
                    if post_link and post_link in processed_post_links:
                        continue  # Skip duplicate PostLink

                    if post_link:
                        processed_post_links.add(post_link)

                    # Get first name only
                    full_name = str(fields.get('InfluencerName', ''))
                    first_name = get_first_name(full_name)

                    # Get campaign details
                    campaign_name = ""
                    try:
                        campaign_details = get_campaign_details(campaign_id)
                        if campaign_details:
                            campaign_name = campaign_details.get('campaignName', campaign_id)
                        else:
                            campaign_name = campaign_id
                    except:
                        campaign_name = campaign_id

                    # Process all error descriptions and remove duplicates
                    all_missing_hashtags = set()
                    all_missing_tags = set()

                    for error_desc in error_descriptions:
                        hashtags, tags = parse_error_description(error_desc)
                        all_missing_hashtags.update(hashtags)
                        all_missing_tags.update(tags)

                    # Create enhanced error message parts
                    error_parts = []
                    if all_missing_hashtags:
                        error_parts.append(f"Missing Hashtags: {', '.join(sorted(all_missing_hashtags))}")
                    if all_missing_tags:
                        error_parts.append(f"Missing Tags: {', '.join(sorted(all_missing_tags))}")

                    # Create formatted suggested message
                    suggested_message = format_suggested_message(first_name, campaign_name, error_parts)

                    # Create issue caption for display
                    all_errors_str = "; ".join(error_parts) if error_parts else "Please review your post"

                    results.append({
                        'postId': post['id'],
                        'influencerName': full_name,
                        'videoLink': post_link or '#',
                        'issueCaption': all_errors_str,
                        'issueVideo': '',
                        'suggestedMessage': suggested_message,
                        'type': 'issues'
                    })

            return jsonify(results)

        elif review_type == 'not_uploaded':
            # Get active influencers associated with the campaign
            all_influencers = influencers_table.get_all()
            active_influencers = {}

            # Get campaign name for messages
            campaign_name = ""
            try:
                campaign_details = get_campaign_details(campaign_id)
                if campaign_details:
                    campaign_name = campaign_details.get('campaignName', campaign_id)
                else:
                    campaign_name = campaign_id
            except:
                campaign_name = campaign_id

            # Filter influencers: Active = YES and associated with the campaign
            active_audited_influencers = {}
            for influencer in all_influencers:
                fields = influencer.get('fields', {})
                if fields.get('Active', '').upper() == 'YES' and fields.get('Audited', '').upper() == 'YES':
                    tiktok_link = fields.get('TiktokLink', '')
                    # active_and_audited.add(tiktok_link)
                    if tiktok_link:
                        # TODO: Add campaign association logic here if you have a specific field
                        # For now, including all active influencers with TikTok links
                        active_audited_influencers[tiktok_link] = influencer

            # Get all posted TikTok links for the campaign
            all_posts = posts_table.get_all()
            posted_tiktok_links = set()

            for post in all_posts:
                fields = post.get('fields', {})
                post_campaign_id = fields.get('CampaignId', '')
                if campaign_value and post_campaign_id != campaign_value:
                    continue

                tiktok_link = fields.get('TikTokLink', '')
                if tiktok_link:
                    posted_tiktok_links.add(tiktok_link)

            # Find active influencers who haven't uploaded yet
            results = []

            for tiktok_link, influencer in active_influencers.items():
                # Only include influencers who haven't uploaded
                if tiktok_link not in posted_tiktok_links:
                    fields = influencer.get('fields', {})
                    full_name = fields.get('Name', 'Unknown Influencer')
                    first_name = get_first_name(full_name)

                    suggested_message = (
                        f"Hi {first_name},\n"
                        f"We noticed you haven't uploaded your video for {campaign_name} yet.\n"
                        f"Please upload it as soon as possible.\n"
                        f"Thanks!"
                    )

                    results.append({
                        'influencerId': influencer['id'],
                        'influencerName': full_name,
                        'tiktokLink': tiktok_link,
                        'instagramLink': fields.get('InstagramLink', '#'),
                        'suggestedMessage': suggested_message,
                        'type': 'not_uploaded'
                    })

            return jsonify(results)

        elif review_type == 'manual_review':
            formula = f"AND({{PostQuality}}='Manual Review', {{CampaignId}}='{campaign_value}')" if campaign_value else "{PostQuality}='Manual Review'"
            manual_review_posts = posts_table.get_all(formula=formula)
            results = []

            for post in manual_review_posts:
                fields = post.get('fields', {})
                full_name = str(fields.get('InfluencerName', ''))
                first_name = get_first_name(full_name)

                results.append({
                    'postId': post['id'],
                    'influencerName': full_name,
                    'videoLink': fields.get('PostLink', '#'),
                    'transcript': fields.get('VideoTranscription', 'No transcript available'),
                    'type': 'manual_review'
                })

            return jsonify(results)
        else:
            return jsonify({'error': 'Invalid review type'}), 400

    except Exception as e:
        app.logger.error(f"Error in get_review_data: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/send_message', methods=['POST'])
def send_message():
    """Handle sending messages to influencers"""
    try:
        data = request.json
        app.logger.info(f"Message sent: {data}")
        return jsonify({
            "status": "success",
            "message": "Message sent successfully"
        })
    except Exception as e:
        app.logger.error(f"Error sending message: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Failed to send message: {str(e)}"
        }), 500

@app.route('/save_comment', methods=['POST'])
def save_comment():
    """Save manager comments for manual reviews"""
    try:
        data = request.json
        post_id = data.get('postId')
        comment = data.get('comment')
        if not post_id or not comment:
            return jsonify({"error": "Missing post ID or comment"}), 400
        app.logger.info(f"Comment saved for post {post_id}: {comment}")
        return jsonify({
            "status": "success",
            "message": "Comment saved successfully"
        })
    except Exception as e:
        app.logger.error(f"Error saving comment: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Failed to save comment: {str(e)}"
        }), 500

@app.route('/get_summary_data')
def get_summary_data():
    """Return summary data as JSON with corrected logic."""
    campaign_id = request.args.get('campaign_id', '')
    try:
        all_posts = posts_table.get_all()
        all_influencers = influencers_table.get_all()
        all_errors = errors_table.get_all()

        # Get campaign value
        campaign_value = ''
        if campaign_id:
            try:
                campaign_record = campaigns_table.get(campaign_id)
                campaign_value = str(campaign_record.get('fields', {}).get('campaignId', ''))
            except Exception as e:
                app.logger.error(f"Could not get campaign value for record {campaign_id}: {e}")
                campaign_value = campaign_id

        # Get active influencers using profile links
        active_influencers = set()
        for influencer in all_influencers:
            fields = influencer.get('fields', {})
            if fields.get('Active', '').upper() == 'YES':
                profile_link = fields.get('TiktokLink', '')
                if profile_link:
                    active_influencers.add(profile_link)

        posts_with_issues = 0
        posts_no_issues = 0
        posts_for_manual_review = 0
        campaign_post_count = 0
        posted_profile_links = set()

        # Loop through posts to categorize them
        for post in all_posts:
            fields = post.get('fields', {})
            post_campaign_id_str = str(fields.get('CampaignId', ''))

            # Apply campaign filter if one is selected
            if campaign_value and post_campaign_id_str != campaign_value:
                continue

            campaign_post_count += 1

            # Track posted profile links
            post_tiktok_link = fields.get('TikTokLink', '')
            if post_tiktok_link:
                posted_profile_links.add(post_tiktok_link)

            # Categorize posts based on PostQuality
            quality = fields.get('PostQuality', '').strip()
            if quality == 'All Correct':
                posts_no_issues += 1
            elif quality == 'Partially Correct/Incorrect':
                posts_with_issues += 1
            # Add other quality conditions as needed

        # Calculate final numbers
        total_influencers = len(active_influencers)
        videos_not_loaded = get_influencers_not_yet_uploaded()

        summary_data = {
            "number_of_influencers": total_influencers,
            "videos_with_no_issues": posts_no_issues,
            "videos_with_issues": posts_with_issues,
            "videos_not_loaded_yet": videos_not_loaded,
            "videos_for_manual_review": posts_for_manual_review,
        }

        return jsonify(summary_data)

    except Exception as e:
        app.logger.error(f"Error in get_summary_data: {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_influencers_not_yet_uploaded():
    active_audited_influencers = set()
    all_influencers = influencers_table.get_all()
    for influencer in all_influencers:
        fields = influencer.get('fields', {})
        if fields.get('Active', '').upper() == 'YES' and fields.get('Audited', '').upper() == 'YES':
            tiktok_link = fields.get('TiktokLink', '')
            active_audited_influencers.add(tiktok_link)

            # Get all posted TikTok links for the campaign
    all_posts = posts_table.get_all()
    posted_tiktok_links = set()
    for post in all_posts:
        fields = post.get('fields', {})
        tiktok_link = fields.get('TikTokLink', '')
        posted_tiktok_links.add(tiktok_link)

    # Find active influencers who haven't uploaded yet
    return len(active_audited_influencers - posted_tiktok_links)


if __name__ == '__main__':
    app.run(debug=True)
