import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import json
import traceback
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# Load environment variables
load_dotenv()

port = int(os.environ.get("PORT", 3000))

# Initialize app with both tokens
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Admin user ID (Rich Luby's ID)
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID")

# Google Docs API Setup
SCOPES = ['https://www.googleapis.com/auth/documents', 
          'https://www.googleapis.com/auth/drive']

# Folder ID where created documents will be stored
DOCS_FOLDER_ID = os.environ.get("DOCS_FOLDER_ID")

def get_google_credentials():
    """Get Google API credentials for both development and production"""
    # Check if running in production (Railway)
    if os.environ.get("RAILWAY_ENVIRONMENT"):
        # Use service account credentials from environment variable
        service_account_info = json.loads(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "{}"))
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES)
        return creds
    else:
        # Local development flow using token.pickle
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
                
        return creds
def create_questionnaire_doc(user_name, user_id):
    """Create a new Google Doc directly with questionnaire content"""
    try:
        # Get credentials
        creds = get_google_credentials()
        
        # Create Drive API client
        drive_service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
        
        # Create Docs API client
        docs_service = googleapiclient.discovery.build('docs', 'v1', credentials=creds)
        
        # 1. Create a blank document
        document = docs_service.documents().create(
            body={'title': f'Career Readiness Questionnaire - {user_name}'}
        ).execute()
        
        document_id = document.get('documentId')
        print(f"Created document with ID: {document_id}")
        
        # 2. Add content to the document
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Define questions list
        QUESTIONS = [
            "1. What do you hope to gain from being a part of this Slack community?",
            "2. Are there any specific career readiness topics you're most interested in improving or learning more about?",
            "3. What career field are you currently in, or what field would you like to pursue?",
            "4. Can you share a bit about your professional background?",
            "5. What job tasks do you excel at and truly enjoy doing?",
            "6. Are there any job tasks that you find challenging or less enjoyable?",
            "7. Are you currently exploring new job opportunities? If so, which cities and states are you focusing on?",
            "8. Share one job you're qualified for that you'd love to have. What excites you about working there?",
            "9. Share one job you're qualified for but wouldn't want to take. Why does it not appeal to you?",
            "10. What industries are you most passionate about or interested in exploring?",
            "11. What is the highest level of education you've completed?",
            "12. Do you have an updated resume ready to go?",
            "13. Is your LinkedIn profile up to date?"
        ]
        
        # Create questionnaire content
        content = f"Career Readiness Questionnaire for {user_name}\nDate Created: {date_str}\n\n"
        content += "Introduction\nThank you for joining our community! This questionnaire will help us understand your career goals and provide personalized support. Please take your time to answer these questions thoughtfully.\n\n"
        content += "Instructions\n1. This document is shared between you and our team\n2. Fill out your answers below each question\n3. Feel free to add comments or ask questions directly in the document\n4. There's no strict deadline, but we recommend completing it within a week\n\n"
        content += "Questionnaire\n\n"
        
        for question in QUESTIONS:
            content += f"{question}\n[Your answer here]\n\n"
        
        content += "\n\nNext Steps\nOnce you've completed this questionnaire, our team will review your responses and may reach out with personalized guidance. We look forward to supporting your career journey!\n\n"
        content += f"For admin use:\nSlack User ID: {user_id}"
        
        # Insert content into the document
        requests = [
            {
                'insertText': {
                    'location': {
                        'index': 1
                    },
                    'text': content
                }
            }
        ]
        
        docs_service.documents().batchUpdate(
            documentId=document_id,
            body={'requests': requests}
        ).execute()
        print(f"Added content to document")
        
        # 3. Try to move to folder if specified
        if DOCS_FOLDER_ID:
            try:
                # First, get the current parents
                file = drive_service.files().get(
                    fileId=document_id, 
                    fields='parents'
                ).execute()
                
                previous_parents = ','.join(file.get('parents', []))
                
                # Move the file to the new folder
                drive_service.files().update(
                    fileId=document_id,
                    addParents=DOCS_FOLDER_ID,
                    removeParents=previous_parents,
                    fields='id, parents'
                ).execute()
                print(f"Moved document to folder with ID: {DOCS_FOLDER_ID}")
            except Exception as folder_error:
                print(f"Error moving to folder: {folder_error}")
                print("Document was created but couldn't be moved to the specified folder")
        else:
            print("No folder ID specified, document will remain in root Drive")
        
        # 4. Share the document with Admin if email is specified
        admin_email = os.environ.get("ADMIN_EMAIL")
        if admin_email:
            try:
                drive_service.permissions().create(
                    fileId=document_id,
                    body={
                        'type': 'user',
                        'role': 'writer',
                        'emailAddress': admin_email
                    }
                ).execute()
                print(f"Shared document with admin: {admin_email}")
            except Exception as share_error:
                print(f"Error sharing document: {share_error}")
        
        # 5. Get the document link
        doc_metadata = drive_service.files().get(
            fileId=document_id,
            fields='webViewLink'
        ).execute()
        
        print(f"Document link: {doc_metadata.get('webViewLink')}")
        return doc_metadata.get('webViewLink')
        
    except Exception as e:
        print(f"Error creating Google Doc: {e}")
        traceback.print_exc()
        return None

# Welcome message blocks - updated with Google Doc info
WELCOME_BLOCKS = [
    {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "🎉 Welcome to the Launch! 🎉",
            "emoji": True
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "This space is *YOURS* – a dynamic community for all things career growth, networking, job opportunities, and more. Whether you're seeking advice, job leads, or connections with like-minded professionals, you're in the right place."
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "Here's your Day 1 checklist to get you started:"
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "1️⃣ *Set Up Your Profile* – Make it personal! Create your username, upload a photo, and share a little about yourself.\n\n2️⃣ *Introduce Yourself* – Head to the @introduction channel and tell us who you are, what you're excited about, and what you're hoping to achieve here.\n\n3️⃣ *Fill Out the Career Readiness Questionnaire* – Check your DMs for a link to your personalized questionnaire."
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "4️⃣ *Explore the Workspace* – Take a tour of our channels! Check out:"
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "• #introduction – Meet others and share your goals\n• #career-advice – Career tips and tricks\n• #networking – Connect with fellow professionals\n• #job-opportunities – Keep an eye out for new roles\n• #resources – All the tools and guides you need\n• #announcements – Stay up to date with important updates and events!\n• #resume-linkedin-review – If you have a resume or a LinkedIn you'd like us to review post it in this channel and specify your asks!"
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "5️⃣ *Post Questions* – Have a question? Drop it in the appropriate channel – we're all here to help each other out!"
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "6️⃣ *Need Help?* – Reach out to <@U0861LS8R8F> for any personal/private career coaching or any Slack support."
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "🔔 *It's go time!*\nLet's kick off the new year with a fresh burst of energy and take our careers to the next level! 💼✨\n\nSee you in the community! 🙋‍♀️🙋‍♂️"
        }
    }
]

def send_questionnaire_link(client, user_id):
    """Send the questionnaire Google Doc link to the user"""
    try:
        # Get user info
        user_info = client.users_info(user=user_id)["user"]
        user_name = user_info["real_name"]
        
        # Create Google Doc for the user
        doc_link = create_questionnaire_doc(user_name, user_id)
        
        if not doc_link:
            # If doc creation failed, notify admin
            notify_admin_of_error(client, user_id, user_name)
            return
        
        # Open DM channel
        response = client.conversations_open(users=[user_id])
        if response["ok"]:
            dm_channel = response["channel"]["id"]
            
            # Send questionnaire link
            client.chat_postMessage(
                channel=dm_channel,
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "Career Readiness Questionnaire",
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Hi {user_name}! Please complete your Career Readiness Questionnaire using the link below. This document is shared with you and our team, so we can collaborate on your career journey."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*<{doc_link}|Click here to open your Career Readiness Questionnaire>*"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Once you've completed the questionnaire, our team will review your responses and may reach out with personalized guidance. Feel free to add comments or questions directly in the document!"
                        }
                    }
                ],
                text=f"Career Readiness Questionnaire: {doc_link}"
            )
            
            # Notify admin that a new questionnaire has been sent
            notify_admin_of_new_questionnaire(client, user_id, user_name, doc_link)
            
    except Exception as e:
        print(f"Error sending questionnaire link: {e}")
        traceback.print_exc()

def notify_admin_of_new_questionnaire(client, user_id, user_name, doc_link):
    """Notify admin about new questionnaire"""
    try:
        # Send to admin
        admin_dm = client.conversations_open(users=[ADMIN_USER_ID])
        if admin_dm["ok"]:
            client.chat_postMessage(
                channel=admin_dm["channel"]["id"],
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"New Questionnaire Sent to {user_name}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"A new Career Readiness Questionnaire has been sent to <@{user_id}>."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*<{doc_link}|View their questionnaire>*"
                        }
                    }
                ],
                text=f"New Questionnaire Sent to {user_name}"
            )
    except Exception as e:
        print(f"Error notifying admin: {e}")
        traceback.print_exc()

def notify_admin_of_error(client, user_id, user_name):
    """Notify admin about a document creation error"""
    try:
        # Send to admin
        admin_dm = client.conversations_open(users=[ADMIN_USER_ID])
        if admin_dm["ok"]:
            client.chat_postMessage(
                channel=admin_dm["channel"]["id"],
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"Error Creating Questionnaire for {user_name}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"There was an error creating a Google Doc for <@{user_id}>. Please check the application logs and create a document manually."
                        }
                    }
                ],
                text=f"Error Creating Questionnaire for {user_name}"
            )
    except Exception as e:
        print(f"Error notifying admin of error: {e}")
        traceback.print_exc()

@app.event("team_join")
def handle_team_join(event, client):
    """Handle new member joining the workspace"""
    try:
        user_id = event["user"]["id"]
        
        # Send welcome message first
        response = client.conversations_open(users=[user_id])
        if response["ok"]:
            dm_channel = response["channel"]["id"]
            client.chat_postMessage(
                channel=dm_channel,
                blocks=WELCOME_BLOCKS,
                text="Welcome to the Launch!"
            )
        
        # Schedule questionnaire link for later
        delay_minutes = 1 if os.environ.get("TEST_MODE", "false").lower() == "true" else 24 * 60
        scheduler.add_job(
            send_questionnaire_link,
            'date',
            run_date=datetime.now() + timedelta(minutes=delay_minutes),
            args=[client, user_id]
        )
        
    except Exception as e:
        print(f"Error in team_join handler: {e}")
        traceback.print_exc()

# Add a test command to manually trigger messages
@app.command("/test-messages")
def test_messages(ack, command, client):
    """Test command to send both welcome and follow-up messages"""
    ack()
    user_id = command['user_id']
    
    try:
        # Send welcome message
        response = client.conversations_open(users=[user_id])
        if response["ok"]:
            dm_channel = response["channel"]["id"]
            client.chat_postMessage(
                channel=dm_channel,
                blocks=WELCOME_BLOCKS,
                text="Welcome to the Launch!"
            )
        
        # Start questionnaire immediately for testing
        send_questionnaire_link(client, user_id)
        
        # Respond in the channel where command was issued
        # Make sure we have a valid channel ID
        channel_id = command.get('channel_id')
        if channel_id:
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    text="Test messages initiated! You'll receive the welcome message and questionnaire link now."
                )
            except Exception as channel_error:
                print(f"Error responding in channel: {channel_error}")
                # Try to DM the user instead
                dm_response = client.conversations_open(users=[user_id])
                if dm_response["ok"]:
                    dm_channel = dm_response["channel"]["id"]
                    client.chat_postMessage(
                        channel=dm_channel,
                        text="Test messages initiated! You'll receive the welcome message and questionnaire link now."
                    )
    except Exception as e:
        print(f"Error in test_messages: {e}")
        traceback.print_exc()

# Add a command to manually send questionnaire to a user
@app.command("/send-questionnaire")
def send_questionnaire_command(ack, command, client):
    """Admin command to send questionnaire to a specific user"""
    ack()
    
    # Only allow admin to use this command
    if command['user_id'] != ADMIN_USER_ID:
        client.chat_postMessage(
            channel=command['channel_id'],
            text="Sorry, only admins can use this command."
        )
        return
    
    # Get the user ID from the command text
    text = command['text'].strip()
    if not text:
        client.chat_postMessage(
            channel=command['channel_id'],
            text="Please specify a user ID or username, e.g., /send-questionnaire @username"
        )
        return
    
    # Extract user ID from the mention format <@U12345>
    if text.startswith('<@') and text.endswith('>'):
        user_id = text[2:-1]
    else:
        # Try to find user by username
        try:
            result = client.users_lookupByEmail(email=text)
            if result["ok"]:
                user_id = result["user"]["id"]
            else:
                client.chat_postMessage(
                    channel=command['channel_id'],
                    text=f"Could not find user: {text}"
                )
                return
        except:
            client.chat_postMessage(
                channel=command['channel_id'],
                text=f"Could not find user: {text}. Please use a valid Slack ID or email."
            )
            return
    
    # Send questionnaire to the user
    send_questionnaire_link(client, user_id)
    
    # Confirm to admin
    client.chat_postMessage(
        channel=command['channel_id'],
        text=f"Questionnaire sent to <@{user_id}>."
    )

# Start the app with Socket Mode
if __name__ == "__main__":
    handler = SocketModeHandler(
        app=app,
        app_token=os.environ.get("SLACK_APP_TOKEN")
    )
    handler.start()