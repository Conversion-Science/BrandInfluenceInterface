# Brand Influence: Influencer Post Tracker Interface

<p align="center">
  <img src="https://placehold.co/600x300/7c3aed/ffffff?text=Brand+Influence+Interface" alt="Project Banner">
</p>

<p align="center">
  <a href="#about-the-project">About</a> •
  <a href="#key-features">Features</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#usage">Usage</a> •
  <a href="#project-structure">Structure</a>
</p>

---

## About The Project

The **Brand Influence Interface** is a web-based application designed to streamline the management and review of influencer marketing campaigns. It provides a centralized hub for campaign managers to monitor posts, identify content issues, and communicate directly with influencers.

This tool bridges a user-friendly web interface, built with **Flask** and hosted on **PythonAnywhere**, with a powerful and flexible **Airtable** database as its backend. It automates the tedious parts of campaign tracking, allowing managers to focus on what matters most: building strong influencer relationships and ensuring high-quality content.

## Key Features

- **Campaign Selection**: Easily switch between different active campaigns.
- **Dashboard Summary**: Get a high-level overview of campaign performance with key metrics:
  - Total active influencers
  - Posts with and without content issues
  - Influencers who have not yet uploaded their content
  - Posts requiring manual review
- **Automated Content Auditing**: Trigger an n8n workflow to automatically audit posts for required tags, hashtags, and other criteria.
- **Unified Review Hub**: A single interface to:
  - Review posts with flagged content issues.
  - View posts that are fully compliant.
  - Track influencers who have not yet posted.
- **Pre-populated Messaging**: Generate templated messages for different scenarios (e.g., content correction requests, approval notifications) to send via WhatsApp.
- **Direct Airtable Integration**: All data is fetched from and saved directly to your Airtable base in real-time.
- **Manager Feedback Loop**: Rate posts on a 5-star scale and leave internal comments for performance tracking.

## Tech Stack

This project is built with a modern and efficient technology stack:

- **Backend**: [Flask](https://flask.palletsprojects.com/) (Python Web Framework)
- **Frontend**: HTML, CSS with [Tailwind CSS](https://tailwindcss.com/), and vanilla JavaScript
- **Database**: [Airtable](https://www.airtable.com/)
- **Hosting**: [PythonAnywhere](https://www.pythonanywhere.com/)
- **Automation (External)**: n8n (for content auditing)

## Getting Started

To get a local copy up and running, or to deploy it on your own PythonAnywhere account, follow these steps.

### Prerequisites

- Python 3.x
- A PythonAnywhere account (or a local environment for development)
- An Airtable account with a base set up according to the required schema.

### Installation & Setup

1.  **Clone the Repository**
    ```sh
    git clone [https://github.com/your-username/BrandInfluenceInterface.git](https://github.com/your-username/BrandInfluenceInterface.git)
    cd BrandInfluenceInterface
    ```

2.  **Install Dependencies**
    ```sh
    pip install -r requirements.txt
    ```
    *(Note: You will need to create a `requirements.txt` file by running `pip freeze > requirements.txt` in your environment after installing the necessary packages like `Flask` and `airtable-python-wrapper`)*

3.  **Set Up Environment Variables**
    The application requires your Airtable API Key and Base ID to function. These should be set as environment variables for security.

    -   **On PythonAnywhere**: Go to the "Web" tab and scroll down to the "Environment variables" section to add them.
    -   **For Local Development**: You can use a `.env` file and a library like `python-dotenv`.

    **Required Variables:**
    -   `AIRTABLE_API_KEY`: Your Airtable API key.
    -   `AIRTABLE_BASE_ID`: The ID of your Airtable base.

4.  **Configure the WSGI File (for PythonAnywhere)**
    In your PythonAnywhere "Web" tab, edit the WSGI configuration file to point to your project's directory and Flask application object.

    ```python
    # /var/www/your-username_pythonanywhere_com_wsgi.py

    import sys

    # Add your project's directory to the Python path
    path = '/home/your-username/BrandInfluenceInterface'
    if path not in sys.path:
        sys.path.insert(0, path)

    # Import the Flask app instance
    from app import app as application
    ```

5.  **Reload the Web App**
    Click the "Reload" button on your PythonAnywhere Web tab to apply the changes.

## Usage

1.  **Campaign Selection**: The initial screen prompts you to select a campaign. You can either start a new audit or view the summary for an existing one.
2.  **Summary Dashboard**: After selecting a campaign, you are taken to the main dashboard which displays real-time statistics.
3.  **Review Queues**: From the dashboard, you can navigate to different review queues:
    -   **Review Posts to Check**: This is a combined view of posts with and without issues. It allows you to quickly work through all uploaded content.
    -   **Message Influencers (Not Uploaded)**: This queue shows all active influencers for the campaign who have not yet posted their content.
4.  **Review Interface**: In the review screen, you can:
    -   View the influencer's name and a link to their post.
    -   See a summary of any flagged content issues.
    -   Use a pre-generated message template.
    -   Click "Send Message" to open WhatsApp Web with the message and contact number pre-filled.
    -   Rate the post and add internal flags or comments.

## Project Structure


BrandInfluenceInterface/
├── app.py                  # Main Flask application, routes, and logic
├── static/
│   └── script.js           # Frontend JavaScript for interactivity
├── templates/
│   ├── campaign_select.html # Campaign selection page
│   └── index.html          # Main dashboard and review interface
├── .gitignore
└── README.md


---

*This interface was developed to enhance the operational efficiency of Brand Influence's campaign management processes.*
