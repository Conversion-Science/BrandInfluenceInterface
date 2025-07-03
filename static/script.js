document.addEventListener('DOMContentLoaded', () => {
    // --- State Management ---
    const state = {
        currentView: 'summary-view',
        data: {
            issues: [],
            not_uploaded: [],
            manual_review: []
        },
        currentIndex: {
            issues: 0,
            not_uploaded: 0,
            manual_review: 0
        },
        currentReviewType: '',
        isLoading: false,
    };

    // --- DOM Elements ---
    const
        messageBox = document.getElementById('message-box'),
        loadingIndicator = document.getElementById('loading-indicator'),
        backToSummaryBtn = document.getElementById('back-to-summary-btn'),
        refreshBtn = document.getElementById('refresh-btn'),
        views = document.querySelectorAll('.view'),
        reviewHeading = document.getElementById('review-heading'),
        activeAuditIndicator = document.getElementById('active-audit'),
        campaignIdInput = document.getElementById('campaign-id');

    // Summary data elements
    const
        totalInfluencersElem = document.getElementById('total-influencers'),
        videosApprovedElem = document.getElementById('videos-approved'),
        videosIssuesElem = document.getElementById('videos-issues'),
        videosNotUploadedElem = document.getElementById('videos-not-uploaded'),
        videosManualReviewElem = document.getElementById('videos-manual-review');

    // Review View Elements
    const
        influencerNameElem = document.getElementById('issues-influencer-name'),
        videoLinkContainer = document.getElementById('video-link-container'),
        videoLinkElem = document.getElementById('issues-video-link'),
        socialProfilesContainer = document.getElementById('social-profiles-container'),
        tiktokLinkElem = document.getElementById('tiktok-link'),
        instagramLinkElem = document.getElementById('instagram-link'),
        issuesContainer = document.getElementById('issues-container'),
        issuesCaptionElem = document.getElementById('issues-caption-issue'),
        transcriptContainer = document.getElementById('transcript-container'),
        transcriptElem = document.getElementById('transcript-text'),
        messageContainer = document.getElementById('message-container'),
        suggestedMessageElem = document.getElementById('issues-message'),
        commentContainer = document.getElementById('comment-container'),
        managerCommentElem = document.getElementById('manager-comment'),
        actionBtn = document.getElementById('action-btn'),
        prevBtn = document.getElementById('issues-prev-btn'),
        nextBtn = document.getElementById('issues-next-btn'),
        issuesContent = document.getElementById('issues-content'),
        issuesEmpty = document.getElementById('issues-empty'),
        issuesCounter = document.getElementById('issues-counter');

    // --- Global Variables ---
    let autoRefreshInterval;
    const currentCampaignId = campaignIdInput ? campaignIdInput.value : '';

    // --- Helper Functions ---
    const showMessage = (msg, type = 'success') => {
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
        loadingIndicator.style.display = loading ? 'block' : 'none';
        if (!loading) {
            document.getElementById(state.currentView).classList.add('active');
        }
    };

    const switchView = (viewId) => {
        state.currentView = viewId;
        views.forEach(v => v.classList.remove('active'));
        document.getElementById(viewId).classList.add('active');
        backToSummaryBtn.style.display = viewId === 'summary-view' ? 'none' : 'block';
    };

    // NEW: Function to fetch and display summary data
    const fetchSummaryData = async () => {
        try {
            // Build URL with campaign ID if present
            let url = '/get_summary_data';
            if (currentCampaignId) {
                url += `?campaign_id=${encodeURIComponent(currentCampaignId)}`;
            }

            console.log('Fetching summary data from:', url);

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Summary data received:', data);

            // Check if there's an error in the response
            if (data.error) {
                throw new Error(data.error);
            }

            // Update the UI elements with the fetched data
            if (totalInfluencersElem) totalInfluencersElem.textContent = data.number_of_influencers || 0;
            if (videosApprovedElem) videosApprovedElem.textContent = data.videos_with_no_issues || 0;
            if (videosIssuesElem) videosIssuesElem.textContent = data.videos_with_issues || 0;
            if (videosNotUploadedElem) videosNotUploadedElem.textContent = data.videos_not_loaded_yet || 0;
            if (videosManualReviewElem) videosManualReviewElem.textContent = data.videos_for_manual_review || 0;

            // Log debug info if available
            if (data.debug_info) {
                console.log('Debug info:', data.debug_info);
            }

        } catch (error) {
            console.error('Error fetching summary data:', error);
            showMessage('Error loading summary data: ' + error.message, 'error');

            // Set all values to show error state
            const errorText = 'Error';
            if (totalInfluencersElem) totalInfluencersElem.textContent = errorText;
            if (videosApprovedElem) videosApprovedElem.textContent = errorText;
            if (videosIssuesElem) videosIssuesElem.textContent = errorText;
            if (videosNotUploadedElem) videosNotUploadedElem.textContent = errorText;
            if (videosManualReviewElem) videosManualReviewElem.textContent = errorText;
        }
    };

    // Start auto-refresh if campaign is selected
    function startAutoRefresh() {
        // Clear existing interval
        if (autoRefreshInterval) clearInterval(autoRefreshInterval);

        // Set new interval (60 seconds)
        autoRefreshInterval = setInterval(() => {
            fetchSummaryData(); // Add this line to refresh summary data
            checkAuditStatus();
        }, 60000);
    }

    // Check if audit is active for current campaign
    async function checkAuditStatus() {
        if (!currentCampaignId) return;

        try {
            const response = await fetch('/audit_status');
            const data = await response.json();

            if (data.active_audits.includes(currentCampaignId)) {
                activeAuditIndicator.classList.remove('hidden');
            } else {
                activeAuditIndicator.classList.add('hidden');
            }
        } catch (error) {
            console.error('Error checking audit status:', error);
        }
    }

    // Fetch data for a specific review type
    const fetchReviewData = async (reviewType) => {
        if (state.isLoading) return;
        setLoading(true);

        try {
            const url = `/get_review_data?type=${reviewType}&campaign_id=${currentCampaignId}`;
            const response = await fetch(url);

            if (!response.ok) throw new Error(`Server responded with status: ${response.status}`);
            const data = await response.json();

            // Log received data for debugging
            console.log(`Received ${reviewType} data:`, data);

            state.data[reviewType] = data;
            state.currentIndex[reviewType] = 0;
            state.currentReviewType = reviewType;

            setLoading(false);
            renderReviewView(reviewType);

        } catch (error) {
            console.error(`Failed to fetch data for ${reviewType}:`, error);
            showMessage('Failed to load data from Airtable. Please try again.', 'error');
            setLoading(false);
            switchView('summary-view');
        }
    };

    // --- Render Functions ---
    const renderReviewView = (reviewType) => {
        switchView('issues-view');
        issuesContent.style.display = 'none';
        issuesEmpty.style.display = 'none';

        const data = state.data[reviewType];
        const index = state.currentIndex[reviewType];

        if (!data || data.length === 0) {
            issuesContent.style.display = 'none';
            issuesEmpty.style.display = 'block';
            issuesEmpty.textContent = `No ${getReviewTypeName(reviewType)} found. Great job!`;
            return;
        }

        issuesContent.style.display = 'block';
        issuesEmpty.style.display = 'none';

        const currentItem = data[index];

        // Set heading based on review type
        reviewHeading.textContent = getReviewTypeName(reviewType);
        issuesCounter.textContent = `${getReviewTypeName(reviewType)} ${index + 1} of ${data.length}`;

        // Reset all containers
        videoLinkContainer.classList.add('hidden');
        socialProfilesContainer.classList.add('hidden');
        issuesContainer.classList.add('hidden');
        transcriptContainer.classList.add('hidden');
        messageContainer.classList.add('hidden');
        commentContainer.classList.add('hidden');

        // Common elements
        influencerNameElem.textContent = currentItem.influencerName || 'Unknown Influencer';

        // Type-specific rendering
        if (reviewType === 'issues') {
            videoLinkContainer.classList.remove('hidden');
            videoLinkElem.href = currentItem.videoLink || '#';
            videoLinkElem.textContent = currentItem.videoLink !== '#' ?
                'View Post' : 'No link available';

            issuesContainer.classList.remove('hidden');
            issuesCaptionElem.textContent = currentItem.issueCaption || 'No issues logged';

            messageContainer.classList.remove('hidden');
            suggestedMessageElem.value = currentItem.suggestedMessage || '';

            actionBtn.textContent = 'Send Message';
            actionBtn.classList.remove('bg-blue-600', 'hover:bg-blue-700');
            actionBtn.classList.add('bg-green-600', 'hover:bg-green-700');
        }
        else if (reviewType === 'not_uploaded') {
            socialProfilesContainer.classList.remove('hidden');
            tiktokLinkElem.href = currentItem.tiktokLink || '#';
            tiktokLinkElem.textContent = currentItem.tiktokLink !== '#' ?
                'View TikTok Profile' : 'No TikTok';
            instagramLinkElem.href = currentItem.instagramLink || '#';
            instagramLinkElem.textContent = currentItem.instagramLink !== '#' ?
                'View Instagram Profile' : 'No Instagram';

            messageContainer.classList.remove('hidden');
            suggestedMessageElem.value = currentItem.suggestedMessage || '';

            actionBtn.textContent = 'Send Message';
            actionBtn.classList.remove('bg-blue-600', 'hover:bg-blue-700');
            actionBtn.classList.add('bg-green-600', 'hover:bg-green-700');
        }
        else if (reviewType === 'manual_review') {
            videoLinkContainer.classList.remove('hidden');
            videoLinkElem.href = currentItem.videoLink || '#';
            videoLinkElem.textContent = currentItem.videoLink !== '#' ?
                'View Post' : 'No link available';

            transcriptContainer.classList.remove('hidden');
            transcriptElem.textContent = currentItem.transcript || 'No transcript available';

            commentContainer.classList.remove('hidden');
            managerCommentElem.value = '';

            actionBtn.textContent = 'Save Comment';
            actionBtn.classList.remove('bg-green-600', 'hover:bg-green-700');
            actionBtn.classList.add('bg-blue-600', 'hover:bg-blue-700');
        }

        // Enable/disable navigation buttons
        prevBtn.disabled = (index <= 0);
        prevBtn.classList.toggle('bg-gray-400', prevBtn.disabled);
        prevBtn.classList.toggle('cursor-not-allowed', prevBtn.disabled);
        prevBtn.classList.toggle('bg-gray-600', !prevBtn.disabled);
        prevBtn.classList.toggle('hover:bg-gray-700', !prevBtn.disabled);

        nextBtn.disabled = (index >= data.length - 1);
        nextBtn.classList.toggle('bg-gray-400', nextBtn.disabled);
        nextBtn.classList.toggle('cursor-not-allowed', nextBtn.disabled);
        nextBtn.classList.toggle('bg-blue-600', !nextBtn.disabled);
        nextBtn.classList.toggle('hover:bg-blue-700', !nextBtn.disabled);
    }

    const getReviewTypeName = (type) => {
        switch(type) {
            case 'issues': return 'Posts with Issues';
            case 'not_uploaded': return 'Videos Not Uploaded';
            case 'manual_review': return 'Video Comments';
            default: return 'Review Item';
        }
    }

    // --- Event Handlers ---
    async function handleAction() {
        const reviewType = state.currentReviewType;
        const index = state.currentIndex[reviewType];
        const currentItem = state.data[reviewType][index];

        if (reviewType === 'issues' || reviewType === 'not_uploaded') {
            // Send message
            const message = suggestedMessageElem.value;

            if (!message.trim()) {
                showMessage('Message cannot be empty', 'error');
                return;
            }

            const payload = {
                type: reviewType,
                influencerName: currentItem.influencerName,
                message: message
            };

            if (reviewType === 'issues') {
                payload.postId = currentItem.postId;
            } else {
                payload.influencerId = currentItem.influencerId;
            }

            try {
                setLoading(true);
                const response = await fetch('/send_message', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();
                setLoading(false);

                if (response.ok) {
                    showMessage(data.message || 'Message sent successfully');
                    // Move to next item after successful send
                    handleNext();
                } else {
                    showMessage(data.error || 'Failed to send message', 'error');
                }
            } catch (error) {
                setLoading(false);
                console.error('Error sending message:', error);
                showMessage('Failed to send message. Please try again.', 'error');
            }
        }
        else if (reviewType === 'manual_review') {
            // Save comment
            const comment = managerCommentElem.value;

            if (!comment.trim()) {
                showMessage('Comment cannot be empty', 'error');
                return;
            }

            const payload = {
                postId: currentItem.postId,
                comment: comment
            };

            try {
                setLoading(true);
                const response = await fetch('/save_comment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();
                setLoading(false);

                if (response.ok) {
                    showMessage(data.message || 'Comment saved successfully');
                    // Move to next item after successful save
                    handleNext();
                } else {
                    showMessage(data.error || 'Failed to save comment', 'error');
                }
            } catch (error) {
                setLoading(false);
                console.error('Error saving comment:', error);
                showMessage('Failed to save comment. Please try again.', 'error');
            }
        }
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

    // --- Initial Setup & Event Listeners ---

    // Attach event listeners
    document.querySelectorAll('.review-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            if (e.target.disabled) return;
            fetchReviewData(e.target.dataset.reviewType);
        });
    });

    backToSummaryBtn.addEventListener('click', handleGoBackToSelection);

    // UPDATED: Refresh button now also refreshes summary data
    refreshBtn.addEventListener('click', () => {
        refreshBtn.querySelector('svg').classList.add('animate-spin');
        fetchSummaryData(); // Refresh summary data instead of reloading page
        setTimeout(() => {
            refreshBtn.querySelector('svg').classList.remove('animate-spin');
        }, 1000);
    });

    nextBtn.addEventListener('click', handleNext);
    prevBtn.addEventListener('click', handlePrev);
    actionBtn.addEventListener('click', handleAction);

    // Initial view load
    switchView('summary-view');

    // NEW: Fetch summary data when page loads
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
        refreshBtn.querySelector('svg').classList.remove('animate-spin');
    }
});
