let whatsappWindow = null;
let windowTimeout = null;

document.addEventListener('DOMContentLoaded', () => {
    // --- State Management ---
    const state = {
        currentView: 'summary-view',
        data: {
            combined: [],
            not_uploaded: [],
            manual_review: []
        },
        currentIndex: {
            combined: 0,
            not_uploaded: 0,
            manual_review: 0
        },
        currentReviewType: '',
        isLoading: false,
    };

    // --- Global Variables ---
    let autoRefreshInterval;
    let currentRatingValue = 0;
    const currentCampaignId = document.getElementById('campaign-id') ?
        document.getElementById('campaign-id').value : '';

    // --- DOM Elements ---
    const messageBox = document.getElementById('message-box'),
        loadingIndicator = document.getElementById('loading-indicator'),
        backToSummaryBtn = document.getElementById('back-to-summary-btn'),
        backToCampaignsBtn = document.getElementById('back-to-campaigns-btn'),
        refreshBtn = document.getElementById('refresh-btn'),
        views = document.querySelectorAll('.view'),
        reviewHeading = document.getElementById('review-heading'),
        activeAuditIndicator = document.getElementById('active-audit'),
        influencerNameElem = document.getElementById('issues-influencer-name'),
        videoLinkContainer = document.getElementById('video-link-container'),
        videoLinkElem = document.getElementById('issues-video-link'),
        socialProfilesContainer = document.getElementById('social-profiles-container'),
        tiktokLinkElem = document.getElementById('tiktok-link'),
        instagramLinkElem = document.getElementById('instagram-link'),
        issuesContainer = document.getElementById('issues-container'),
        issuesCaptionElem = document.getElementById('issues-caption-issue'),
        flagContainer = document.getElementById('flag-container'),
        flagSelect = document.getElementById('flag-select'),
        transcriptContainer = document.getElementById('transcript-container'),
        transcriptElem = document.getElementById('transcript-text'),
        messageContainer = document.getElementById('message-container'),
        suggestedMessageElem = document.getElementById('issues-message'),
        commentContainer = document.getElementById('comment-container'),
        managerCommentElem = document.getElementById('manager-comment'),
        ratingContainer = document.getElementById('rating-container'),
        actionBtn = document.getElementById('action-btn'),
        prevBtn = document.getElementById('issues-prev-btn'),
        nextBtn = document.getElementById('issues-next-btn'),
        issuesContent = document.getElementById('issues-content'),
        issuesEmpty = document.getElementById('issues-empty'),
        issuesCounter = document.getElementById('issues-counter'),
        totalInfluencersElem = document.getElementById('total-influencers'),
        videosApprovedElem = document.getElementById('videos-approved'),
        videosIssuesElem = document.getElementById('videos-issues'),
        videosNotUploadedElem = document.getElementById('videos-not-uploaded'),
        videosManualReviewElem = document.getElementById('videos-manual-review');

    // --- Helper Functions ---
    function getCurrentItem() {
    const reviewType = state.currentReviewType;
    if (!reviewType) return null;

    const index = state.currentIndex[reviewType];
    const data = state.data[reviewType] || [];
    return data[index] || null;
}

function getFirstName(fullName) {
    if (!fullName) return "Unknown";
    if (fullName.includes(',')) {
        return fullName.split(',')[0].trim() || fullName.split(',')[1].trim();
    }
    return fullName.split(' ')[0].trim();
}

function generateMessage(currentItem, flag) {
    if (!currentItem) return "";

    const firstName = getFirstName(currentItem.influencerName);
    const campaignName = currentItem.campaignName || 'the campaign';
    const postLink = currentItem.videoLink || 'your post';

    let messageLines = [];

    if (flag === 'Video Ok') {
        messageLines = [
            `Hi ${firstName},`,
            `We are confirming that your recent post for ${campaignName} is approved:`,
            `View it here: <a href="${postLink}">Link</a>`,
            // `It can remain online.`,
            `Thanks!`
        ];
    } else if (flag === 'Take Down Video') {
        messageLines = [
            `Hi ${firstName},`,
            `We are issuing a takedown notice for your recent post for ${campaignName}:`,
            `Reason: ${currentItem.issueCaption || 'Content policy violation'}`,
            `View it here: ${postLink}`,
            `Please take it down promptly.`,
            `Thanks!`
        ];
    } else if (currentItem?.hasIssues) {
        messageLines = [
            `Hi ${firstName},`,
            `We noticed issues with your recent post for ${campaignName}:`,
            currentItem.issueCaption || 'Please review your post',
            `View it here: ${postLink}`,
            `Please review and update.`,
            `Thanks!`
        ];
    } else {
        messageLines = [
            `Hi ${firstName},`,
            `Great job on your recent post for ${campaignName}!`,
            `Your content looks perfect and meets all requirements.`,
            `Thank you for your excellent work!`,
            `Keep it up!`
        ];
    }
    return messageLines.join('\n');
}

    const showMessage = (msg, type = 'success') => {
        if (!messageBox) return;
        messageBox.textContent = msg;
        messageBox.className = `fixed top-5 right-5 p-4 rounded-lg shadow-xl text-white z-50 transition-transform transform ${type === 'success' ? 'bg-green-500' : 'bg-red-500'}`;
        messageBox.classList.remove('hidden', 'translate-x-full');
        setTimeout(() => {
            messageBox.style.transform = 'translateX(0)';
        }, 10);

        setTimeout(() => {
            messageBox.style.transform = 'translateX(120%)';
        }, 4000);
    };

    const setLoading = (loading) => {
        state.isLoading = loading;
        views.forEach(v => v.classList.remove('active'));
        if (loadingIndicator) {
            loadingIndicator.style.display = loading ? 'block' : 'none';
        }
        if (!loading) {
            const currentView = document.getElementById(state.currentView);
            if (currentView) {
                currentView.classList.add('active');
            }
        }
    };

    const switchView = (viewId) => {
        state.currentView = viewId;
        views.forEach(v => v.classList.remove('active'));
        const viewElement = document.getElementById(viewId);
        if (viewElement) {
            viewElement.classList.add('active');
        }

        // Hide Back to Campaigns button in review view, show in summary view
        if (backToCampaignsBtn) {
            backToCampaignsBtn.style.display = viewId === 'summary-view' ? 'block' : 'none';
        }

        // Show Back to Summary button only in review views
        if (backToSummaryBtn) {
            backToSummaryBtn.style.display = viewId === 'summary-view' ? 'none' : 'block';
        }
    };

    function updateRatingStars(rating) {
        const stars = document.querySelectorAll('.rating-stars span');
        stars.forEach((star, index) => {
            if (index < rating) {
                star.textContent = '★';
                star.style.color = '#f59e0b';
            } else {
                star.textContent = '☆';
                star.style.color = '#9ca3af';
            }
        });
        const ratingValue = document.getElementById('rating-value');
        if (ratingValue) {
            ratingValue.textContent = `(${rating})`;
        }
    }

    // Fetch summary data
    const fetchSummaryData = async () => {
        try {
            let url = '/get_summary_data';
            if (currentCampaignId) {
                url += `?campaign_id=${encodeURIComponent(currentCampaignId)}`;
            }

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (totalInfluencersElem) totalInfluencersElem.textContent = data.number_of_influencers || 0;
            if (videosApprovedElem) videosApprovedElem.textContent = data.videos_with_no_issues || 0;
            if (videosIssuesElem) videosIssuesElem.textContent = data.videos_with_issues || 0;
            if (videosNotUploadedElem) videosNotUploadedElem.textContent = data.videos_not_loaded_yet || 0;
            if (videosManualReviewElem) videosManualReviewElem.textContent = data.videos_for_manual_review || 0;

        } catch (error) {
            console.error('Error fetching summary data:', error);
            showMessage('Error loading summary data: ' + error.message, 'error');
            const errorText = '--';
            if (totalInfluencersElem) totalInfluencersElem.textContent = errorText;
            if (videosApprovedElem) videosApprovedElem.textContent = errorText;
            if (videosIssuesElem) videosIssuesElem.textContent = errorText;
            if (videosNotUploadedElem) videosNotUploadedElem.textContent = errorText;
            if (videosManualReviewElem) videosManualReviewElem.textContent = errorText;
        }
    };

    // Start auto-refresh
    function startAutoRefresh() {
        if (autoRefreshInterval) clearInterval(autoRefreshInterval);
        autoRefreshInterval = setInterval(() => {
            fetchSummaryData();
            checkAuditStatus();
        }, 60000);
    }

    // Check audit status
    async function checkAuditStatus() {
        if (!currentCampaignId) return;
        try {
            const response = await fetch('/audit_status');
            const data = await response.json();
            if (activeAuditIndicator) {
                if (data.active_audits.includes(currentCampaignId)) {
                    activeAuditIndicator.classList.remove('hidden');
                } else {
                    activeAuditIndicator.classList.add('hidden');
                }
            }
        } catch (error) {
            console.error('Error checking audit status:', error);
        }
    }

    // Fetch review data
const fetchReviewData = async (reviewType) => {
    if (state.isLoading) return;
    setLoading(true);

    try {
        // Encode parameters to handle special characters
        const url = `/get_review_data?type=${encodeURIComponent(reviewType)}&campaign_id=${encodeURIComponent(currentCampaignId)}`;
        const response = await fetch(url);

        if (!response.ok) {
            // Try to get error details from response
            let errorMsg = `Server responded with status: ${response.status}`;
            try {
                const errorData = await response.json();
                if (errorData.error) {
                    errorMsg = errorData.error;
                }
            } catch (e) {
                // Ignore JSON parsing errors
            }
            throw new Error(errorMsg);
        }

        const data = await response.json();
        state.data[reviewType] = data;
        state.currentIndex[reviewType] = 0;
        state.currentReviewType = reviewType;

        setLoading(false);
        renderReviewView(reviewType);

    } catch (error) {
        console.error(`Failed to fetch data for ${reviewType}:`, error);
        showMessage(`Failed to load data: ${error.message}`, 'error');
        setLoading(false);
        switchView('summary-view');
    }
};

const renderReviewView = (reviewType) => {
    switchView('issues-view');

    // Move currentItem declaration to the top
    const data = state.data[reviewType] || [];
    const index = state.currentIndex[reviewType] || 0;
    const currentItem = (index >= 0 && index < data.length) ? data[index] : null;

    // Check if we have valid data
    if (!data || data.length === 0) {
        if (issuesContent) issuesContent.style.display = 'none';
        if (issuesEmpty) {
            issuesEmpty.style.display = 'block';
            issuesEmpty.textContent = `No ${getReviewTypeName(reviewType)} found. Great job!`;
        }
        return;
    }

    // Now currentItem is properly defined before use
    const reviewedTag = document.getElementById('reviewed-tag');
    if (reviewedTag) {
        reviewedTag.style.display = currentItem?.reviewed ? 'block' : 'none';
    }

    // Check if we have a valid currentItem
    if (!currentItem) {
        if (issuesContent) issuesContent.style.display = 'none';
        if (issuesEmpty) {
            issuesEmpty.style.display = 'block';
            issuesEmpty.textContent = `No items to review in ${getReviewTypeName(reviewType)}`;
        }
        return;
    }

    if (issuesContent) issuesContent.style.display = 'block';
    if (issuesEmpty) issuesEmpty.style.display = 'none';

    // Set influencer name safely
    if (influencerNameElem) influencerNameElem.textContent = currentItem.influencerName || 'Unknown Influencer';

    // Set heading
    if (reviewHeading) reviewHeading.textContent = getReviewTypeName(reviewType);
    if (issuesCounter) issuesCounter.textContent = `${getReviewTypeName(reviewType)} ${index + 1} of ${data.length}`;

    // Reset all containers
    if (videoLinkContainer) videoLinkContainer.classList.add('hidden');
    if (socialProfilesContainer) socialProfilesContainer.classList.add('hidden');
    if (issuesContainer) issuesContainer.classList.add('hidden');
    if (flagContainer) flagContainer.classList.add('hidden');
    if (transcriptContainer) transcriptContainer.classList.add('hidden');
    if (messageContainer) messageContainer.classList.add('hidden');
    if (commentContainer) commentContainer.classList.add('hidden');
    if (ratingContainer) ratingContainer.classList.add('hidden');

    // Approval container moved to the bottom
    const approvalContainer = document.getElementById('approval-container');
    if (approvalContainer) approvalContainer.classList.add('hidden');

    // Type-specific rendering
    if (reviewType === 'not_uploaded') {
        if (socialProfilesContainer) socialProfilesContainer.classList.remove('hidden');
        if (tiktokLinkElem) {
            tiktokLinkElem.href = currentItem.tiktokLink || '#';
            tiktokLinkElem.textContent = currentItem.tiktokLink !== '#' ? 'View TikTok Profile' : 'No TikTok';
        }
        if (instagramLinkElem) {
            instagramLinkElem.href = currentItem.instagramLink || '#';
            instagramLinkElem.textContent = currentItem.instagramLink !== '#' ? 'View Instagram Profile' : 'No Instagram';
        }

        if (messageContainer) messageContainer.classList.remove('hidden');
        if (suggestedMessageElem) suggestedMessageElem.value = currentItem.suggestedMessage || '';

        if (actionBtn) {
            actionBtn.textContent = 'Send Message';
            actionBtn.classList.remove('bg-blue-600', 'hover:bg-blue-700');
            actionBtn.classList.add('bg-green-600', 'hover:bg-green-700');
        }
    }
    else if (reviewType === 'manual_review') {
        if (videoLinkContainer) videoLinkContainer.classList.remove('hidden');
        if (videoLinkElem) {
            videoLinkElem.href = currentItem.videoLink || '#';
            videoLinkElem.textContent = currentItem.videoLink !== '#' ? 'View Post' : 'No link available';
        }

        if (transcriptContainer) transcriptContainer.classList.remove('hidden');
        if (transcriptElem) transcriptElem.textContent = currentItem.transcript || 'No transcript available';

        if (commentContainer) commentContainer.classList.remove('hidden');
        if (managerCommentElem) managerCommentElem.value = '';

        // Show flag and rating
        if (flagContainer) {
            flagContainer.classList.remove('hidden');
            if (flagSelect) flagSelect.value = currentItem.currentFlag || '';
        }
        if (ratingContainer) {
            ratingContainer.classList.remove('hidden');
            currentRatingValue = currentItem.currentRating || 0;
            updateRatingStars(currentRatingValue);
        }

        if (actionBtn) {
            actionBtn.textContent = 'Save Comment';
            actionBtn.classList.remove('bg-green-600', 'hover:bg-green-700');
            actionBtn.classList.add('bg-blue-600', 'hover:bg-blue-700');
        }
    }
    else if (reviewType === 'issues' || reviewType === 'combined') {
        if (videoLinkContainer) videoLinkContainer.classList.remove('hidden');
        if (videoLinkElem) {
            videoLinkElem.href = currentItem.videoLink || '#';
            videoLinkElem.textContent = currentItem.videoLink !== '#' ? 'View Post' : 'No link available';
        }

        // For combined view, show either issues or comment
        if (reviewType === 'combined') {
            if (currentItem.hasIssues) {
                if (issuesContainer) issuesContainer.classList.remove('hidden');
                if (issuesCaptionElem) issuesCaptionElem.textContent = currentItem.issueCaption || 'No issues logged';
                if (commentContainer) commentContainer.classList.add('hidden');
            } else {
                if (issuesContainer) issuesContainer.classList.add('hidden');
                if (commentContainer) commentContainer.classList.remove('hidden');
                if (managerCommentElem) managerCommentElem.value = '';
            }
        } else {
            // For issues-only view
            if (issuesContainer) issuesContainer.classList.remove('hidden');
            if (issuesCaptionElem) issuesCaptionElem.textContent = currentItem.issueCaption || 'No issues logged';
        }

        // Show flag and rating
        if (flagContainer) {
            flagContainer.classList.remove('hidden');
            if (flagSelect) flagSelect.value = currentItem.currentFlag || '';
        }
        if (ratingContainer) {
            ratingContainer.classList.remove('hidden');
            currentRatingValue = currentItem.currentRating || 0;
            updateRatingStars(currentRatingValue);
        }

        if (messageContainer) messageContainer.classList.remove('hidden');
        if (suggestedMessageElem) suggestedMessageElem.value = currentItem.suggestedMessage || '';

        // Set button text based on post type
        if (actionBtn) {
            if (reviewType === 'combined' && !currentItem.hasIssues) {
                actionBtn.textContent = 'Save Comment and Rating';
                actionBtn.classList.remove('bg-green-600', 'hover:bg-green-700');
                actionBtn.classList.add('bg-blue-600', 'hover:bg-blue-700');
            } else {
                actionBtn.textContent = 'Send Message';
                actionBtn.classList.remove('bg-blue-600', 'hover:bg-blue-700');
                actionBtn.classList.add('bg-green-600', 'hover:bg-green-700');
            }
        }

        // Add approval section at the bottom for approved posts
        if (reviewType === 'combined' && !currentItem.hasIssues && approvalContainer) {
            approvalContainer.classList.remove('hidden');
            const approvalStatus = document.getElementById('approval-status-value');
            const approveBtn = document.getElementById('approve-btn');

            if (currentItem.approved_Status === 'YES') {
                approvalStatus.textContent = 'Approved';
                approvalStatus.className = 'font-semibold text-green-600';
                approveBtn.textContent = 'Approved';
                approveBtn.disabled = true;
                approveBtn.classList.remove('bg-green-600', 'hover:bg-green-700');
                approveBtn.classList.add('bg-gray-400', 'cursor-not-allowed');
            } else {
                approvalStatus.textContent = 'Not Approved';
                approvalStatus.className = 'font-semibold text-red-600';
                approveBtn.textContent = 'Approve Post';
                approveBtn.disabled = false;
                approveBtn.classList.add('bg-green-600', 'hover:bg-green-700');
                approveBtn.classList.remove('bg-gray-400', 'cursor-not-allowed');
            }
        }
    }

    // Enable/disable navigation buttons
    if (prevBtn && nextBtn) {
        prevBtn.disabled = (index <= 0);
        nextBtn.disabled = (index >= data.length - 1);

        prevBtn.classList.toggle('bg-gray-400', prevBtn.disabled);
        prevBtn.classList.toggle('cursor-not-allowed', prevBtn.disabled);
        prevBtn.classList.toggle('bg-gray-600', !prevBtn.disabled);
        prevBtn.classList.toggle('hover:bg-gray-700', !prevBtn.disabled);

        nextBtn.classList.toggle('bg-gray-400', nextBtn.disabled);
        nextBtn.classList.toggle('cursor-not-allowed', nextBtn.disabled);
        nextBtn.classList.toggle('bg-blue-600', !nextBtn.disabled);
        nextBtn.classList.toggle('hover:bg-blue-700', !nextBtn.disabled);

        // Change text for last post
        if (index >= data.length - 1) {
            nextBtn.textContent = 'Finished';
        } else {
            nextBtn.textContent = 'Next Post →';
        }
    }

    // Combine save and next functionality
    if (actionBtn && (reviewType === 'issues' || reviewType === 'combined')) {
        actionBtn.addEventListener('click', async function() {
            // Save changes first
            await handleSaveChanges();

            // Then move to next post
            if (index < data.length - 1) {
                state.currentIndex[reviewType]++;
                renderReviewView(reviewType);
            } else {
                // For last post, change button to "Finished"
                nextBtn.textContent = 'Finished';
                nextBtn.disabled = false;
                showMessage('Review completed!', 'success');
            }
        });
    }
};

    const getReviewTypeName = (type) => {
        switch(type) {
            case 'issues':
            case 'combined':
                return 'Posts to Check';
            case 'not_uploaded': return 'Videos Not Uploaded';
            case 'manual_review': return 'Video Comments';
            default: return 'Review Item';
        }
    }

async function handleSaveChanges() {
    const reviewType = state.currentReviewType;
    const index = state.currentIndex[reviewType];
    const data = state.data[reviewType] || [];
    const currentItem = (index >= 0 && index < data.length) ? data[index] : null;

    if (!currentItem) return;

    try {
        // Save flag if changed
        if (flagSelect && flagSelect.value !== currentItem.currentFlag) {
            await fetch('/save_flag', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    postId: currentItem.postId,
                    flag: flagSelect.value
                })
            });
            currentItem.currentFlag = flagSelect.value;
        }

        // Save rating if changed
        if (currentRatingValue !== currentItem.currentRating) {
            await fetch('/save_rating', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    postId: currentItem.postId,
                    rating: currentRatingValue
                })
            });
            currentItem.currentRating = currentRatingValue;
        }

        // Mark as reviewed
        await fetch('/mark_reviewed', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                postId: currentItem.postId,
                reviewed: true
            })
        });
        currentItem.reviewed = true;

        // Confirmation for reviewed posts
        if (currentItem.reviewed && currentItem.approved_Status === 'YES') {
            if (!confirm('This post has been reviewed and approved. Are you sure you want to update your selection?')) {
                // Revert changes if user cancels
                if (flagSelect) flagSelect.value = currentItem.currentFlag;
                currentRatingValue = currentItem.currentRating;
                updateRatingStars(currentRatingValue);
                return;
            }
        }

        showMessage('Changes saved successfully!');
    } catch (error) {
        console.error('Save error:', error);
        showMessage('Failed to save changes', 'error');
    }
}


async function handleAction() {
    const reviewType = state.currentReviewType;
    if (!reviewType) return;

    const index = state.currentIndex[reviewType];
    const currentItem = state.data[reviewType][index];

    if (!currentItem) {
        showMessage('No item to review.', 'error');
        return;
    }

    // --- Logic for Sending a Message ---
    if (reviewType === 'not_uploaded' || (currentItem && currentItem.hasIssues)) {
        const message = suggestedMessageElem.value;
        if (!message.trim()) {
            showMessage('Message cannot be empty.', 'error');
            return;
        }
        encodedMessage = encodeURIComponent(message);

        // The backend must provide the contactNumber in the data payload
        let phoneNumber = currentItem.contactNumber;
        if (!phoneNumber) {
            showMessage('Contact number not found for this influencer.', 'error');
            return;
        }

        // --- NEW: Copy message to clipboard as a reliable fallback ---
        try {
            // Create a temporary textarea to hold the message
            const textArea = document.createElement("textarea");
            textArea.value = message;
            // Make the textarea invisible
            textArea.style.position = "fixed";
            textArea.style.left = "-9999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            document.execCommand('copy'); // Use the browser's copy command
            document.body.removeChild(textArea);

            // --- WhatsApp Logic ---
            // Format phone number
            phoneNumber = String(phoneNumber).replace(/[^\d+]/g, '');
            if (phoneNumber.startsWith('0')) {
                phoneNumber = '+27' + phoneNumber.substring(1);
            } else if (!phoneNumber.startsWith('+')) {
                phoneNumber = '+' + phoneNumber;
            }

            // Construct the direct link to open the app
            const whatsappUrl = `https://web.whatsapp.com/send?phone=${phoneNumber}&text=${encodedMessage}`;
            // const whatsappUrl = `whatsapp://send?phone=${phoneNumber}&text=${encodedMessage}`;


            // Clear any existing timeout
            if (windowTimeout) {
                clearTimeout(windowTimeout);
                windowTimeout = null;
            }

            let shouldOpenNew = true;

            // Check if we can reuse the existing window
            if (whatsappWindow && !whatsappWindow.closed) {
                    try {
                        // Update existing window
                        whatsappWindow.location.href = whatsappUrl;
                        whatsappWindow.focus();
                        shouldOpenNew = false;
                    } catch (e) {
                        // Security error - can't access window from different origin
                        console.log('Cannot access window, opening new one');
                    }
                }

            // Set timeout to clear window reference after 5 minutes
if (shouldOpenNew) {
        whatsappWindow = window.open(whatsappUrl, 'whatsappWindow');

        // Set timeout to clear window reference after 1 hour
        windowTimeout = setTimeout(() => {
            whatsappWindow = null;
        }, 60 * 60 * 1000); // 1 hour
    }

            // Move to the next item after a short delay to allow the app to open
            setTimeout(() => handleNav(1), 2000);

        } catch (err) {
            console.error('Failed to copy message: ', err);
            showMessage('Could not copy message. Please copy it manually.', 'error');
        }

        // Move to next item after sending
        handleNext();
    }
    else if (reviewType === 'manual_review' ||
            (reviewType === 'combined' && !currentItem.hasIssues)) {
        // Save comment and rating
        const comment = managerCommentElem ? managerCommentElem.value : '';
        const rating = currentRatingValue;

        if (!comment.trim() && rating === 0) {
            showMessage('Please provide a comment or rating', 'error');
            return;
        }

        try {
            setLoading(true);

            // Save comment if provided
            if (comment.trim()) {
                const commentPayload = {
                    postId: currentItem.postId,
                    comment: comment
                };
                await fetch('/save_comment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(commentPayload)
                });
            }

            // Save rating if provided
            if (rating > 0) {
                const ratingPayload = {
                    postId: currentItem.postId,
                    rating: rating
                };
                await fetch('/save_rating', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(ratingPayload)
                });
            }

            setLoading(false);
            showMessage('Post reviewed. Moving to next.', 'success');
            handleNav(1);
        } catch (error) {
            setLoading(false);
            console.error('Error saving comment and rating:', error);
            showMessage('Failed to save. Please try again.', 'error');
        }
    }
}

    function cleanPhoneNumber(phone) {
        return phone.replace(/\D/g, '');
    }

    function handleNext() {
        const reviewType = state.currentReviewType;
        if (state.currentIndex[reviewType] < state.data[reviewType].length - 1) {
            state.currentIndex[reviewType]++;
            renderReviewView(reviewType);
        }
    }

    function handlePrev() {
        const reviewType = state.currentReviewType;
        if (state.currentIndex[reviewType] > 0) {
            state.currentIndex[reviewType]--;
            renderReviewView(reviewType);
        }
    }

    function handleGoBackToSelection() {
        switchView('summary-view');
    }

    // Handle flag change
    async function handleFlagChange() {
        const flag = this.value;
        const reviewType = state.currentReviewType;
        const index = state.currentIndex[reviewType];
        const currentItem = state.data[reviewType][index];

        if (!currentItem.postId) return;

        try {
            const response = await fetch('/save_flag', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    postId: currentItem.postId,
                    flag: flag
                })
            });

            const data = await response.json();
            if (response.ok) {
                showMessage('Flag saved successfully');
                // Update current state
                currentItem.currentFlag = flag;
            } else {
                showMessage('Error saving flag: ' + (data.message || ''), 'error');
            }
        } catch (error) {
            console.error('Error saving flag:', error);
            showMessage('Failed to save flag', 'error');
        }
    }

    // --- Initial Setup & Event Listeners ---

    document.getElementById('approve-btn').addEventListener('click', async function() {
    const reviewType = state.currentReviewType;
    const index = state.currentIndex[reviewType];
    const currentItem = state.data[reviewType][index];

    try {
        const response = await fetch('/approve_post', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                postId: currentItem.postId,
                status: 'YES'
            })
        });

        if (response.ok) {
            showMessage('Post approved!');
            currentItem.approved_Status = 'YES';
            renderReviewView(reviewType);
        } else {
            showMessage('Error approving post', 'error');
        }
    } catch (error) {
        console.error('Approval error:', error);
        showMessage('Failed to approve post', 'error');
    }
});


    document.addEventListener('click', function(e) {
        if (e.target && e.target.id === 'action-btn') {
            handleAction();
        }
    });

    // Attach event listeners
    document.querySelectorAll('.review-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            if (e.target.disabled) return;
            fetchReviewData(e.target.dataset.reviewType);
        });
    });

    if (backToSummaryBtn) {
        backToSummaryBtn.addEventListener('click', handleGoBackToSelection);
    }

    if (backToCampaignsBtn) {
        backToCampaignsBtn.addEventListener('click', () => {
            window.location.href = "https://jay1dev.pythonanywhere.com/campaign_select";
        });
    }

    // Star rating event listeners
    // Add this inside the star click handler
    document.querySelectorAll('.rating-stars span').forEach(star => {
        star.addEventListener('click', function() {
            const rating = parseInt(this.getAttribute('data-rating'));
            currentRatingValue = rating;
            updateRatingStars(rating);

            // Immediately save the rating
            const reviewType = state.currentReviewType;
            const index = state.currentIndex[reviewType];
            const currentItem = state.data[reviewType][index];

            if (currentItem.postId) {
                fetch('/save_rating', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        postId: currentItem.postId,
                        rating: rating
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === "success") {
                        showMessage('Rating saved');
                    } else {
                        showMessage('Error saving rating', 'error');
                    }
                })
                .catch(error => {
                    console.error('Error saving rating:', error);
                    showMessage('Failed to save rating', 'error');
                });
            }
        });
    });

    // Flag change event listener
if (flagSelect) {
    flagSelect.addEventListener('change', function() {
        const reviewType = state.currentReviewType;
        const index = state.currentIndex[reviewType];
        const data = state.data[reviewType] || [];
        const currentItem = (index >= 0 && index < data.length) ? data[index] : null;

        if (currentItem && suggestedMessageElem) {
            suggestedMessageElem.value = generateMessage(currentItem, this.value);
        }
    });
}

    // Refresh button
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            const svg = refreshBtn.querySelector('svg');
            if (svg) svg.classList.add('animate-spin');
            fetchSummaryData();
            setTimeout(() => {
                if (svg) svg.classList.remove('animate-spin');
            }, 1000);
        });
    }

    if (nextBtn) nextBtn.addEventListener('click', handleNext);
    if (prevBtn) prevBtn.addEventListener('click', handlePrev);
    if (actionBtn) actionBtn.addEventListener('click', handleAction);

    // Initial view load
    switchView('summary-view');
    fetchSummaryData();

    // Start auto-refresh if campaign is selected
    if (currentCampaignId) {
        startAutoRefresh();
        checkAuditStatus();
    }
});

// Remove animation class when refresh completes
window.addEventListener('load', () => {
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        const svg = refreshBtn.querySelector('svg');
        if (svg) svg.classList.remove('animate-spin');
    }
});
