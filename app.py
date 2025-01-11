import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import json

# Load environment variables
load_dotenv()

# Initialize app with both tokens
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Admin user ID (Rich Luby's ID)
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID")

# Store user's current question state
user_states = {}

# Welcome message blocks
WELCOME_BLOCKS = [
    {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Welcome to the Launch! 🚀",
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
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Your Day 1 Checklist:",
            "emoji": True
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*1. Set Up Your Profile* – Make it personal! Create your username, upload a photo, and share a little about yourself.\n\n*2. Introduce Yourself* – Head to the #introduction channel and tell us who you are, what you're excited about, and what you're hoping to achieve here.\n\n*3. Fill Out the Career Readiness Questionnaire* – Check your DMs from <@U0861LS8R8F> and complete the questionnaire so we can support you in the best way possible."
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*4. Explore the Workspace* – Take a tour of our channels!"
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "• #introduction – Meet others and share your goals\n• #career-advice – Career tips and tricks\n• #networking – Connect with fellow professionals\n• #job-opportunities – Keep an eye out for new roles\n• #resources – All the tools and guides you need\n• #announcements – Stay up to date with important updates and events!"
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*5. Post Questions* – Have a question? Drop it in the appropriate channel – we're all here to help each other out!"
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Need Help?* – Reach out to @Rich Luby for any personal/private career coaching or any Slack support."
        }
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*It's go time!* 🎉\nLet's kick off the new year with a fresh burst of energy and take our careers to the next level!\n\nSee you in the community!"
        }
    }
]

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

def create_question_block(question_num):
    """Create a message block for a question"""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Question {question_num + 1} of {len(QUESTIONS)}*\n{QUESTIONS[question_num]}"
            }
        },
        {
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "action_id": "question_response",
                "multiline": True
            },
            "label": {
                "type": "plain_text",
                "text": "Your Response"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Submit Response"
                    },
                    "action_id": "submit_response"
                }
            ]
        }
    ]

def send_questionnaire_start(client, user_id):
    """Send the initial questionnaire message"""
    try:
        # Initialize user state
        user_states[user_id] = {
            "current_question": 0,
            "responses": []
        }
        
        # Open DM channel
        response = client.conversations_open(users=[user_id])
        if response["ok"]:
            dm_channel = response["channel"]["id"]
            
            # Send introduction message
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
                            "text": "Welcome! Please take a moment to answer these questions to help us better understand your career goals and needs."
                        }
                    }
                ]
            )
            
            # Send first question
            client.chat_postMessage(
                channel=dm_channel,
                blocks=create_question_block(0)
            )
            
    except Exception as e:
        print(f"Error starting questionnaire: {e}")

@app.action("submit_response")
def handle_submission(ack, body, client):
    """Handle when a user submits a response"""
    print("Received submission. Body:", json.dumps(body, indent=2))
    ack()
    try:
        user_id = body["user"]["id"]
        channel_id = body["container"]["channel_id"]
        
        # Get the response text from the input
        block_id = list(body["state"]["values"].keys())[0]  # Get the first (and only) block ID
        response_text = body["state"]["values"][block_id]["question_response"]["value"]
        
        # Store the response
        current_q = user_states[user_id]["current_question"]
        user_states[user_id]["responses"].append({
            "question": QUESTIONS[current_q],
            "response": response_text
        })
        
        # Move to next question or finish
        current_q += 1
        user_states[user_id]["current_question"] = current_q
        
        if current_q < len(QUESTIONS):
            # Send next question
            client.chat_postMessage(
                channel=channel_id,
                blocks=create_question_block(current_q)
            )
        else:
            # Questionnaire complete
            send_completion_messages(client, user_id, channel_id)
            
    except Exception as e:
        print(f"Error handling submission: {e}")

def send_completion_messages(client, user_id, channel_id):
    """Send completion messages to user and admin"""
    try:
        # Thank the user
        client.chat_postMessage(
            channel=channel_id,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Thank you for completing the questionnaire! Your responses have been recorded."
                    }
                }
            ]
        )
        
        # Format responses for admin
        responses = user_states[user_id]["responses"]
        formatted_responses = "\n\n".join([
            f"*{resp['question']}*\n{resp['response']}"
            for resp in responses
        ])
        
        # Get user info
        user_info = client.users_info(user=user_id)["user"]
        user_name = user_info["real_name"]
        
        # Send to admin (Rich)
        admin_dm = client.conversations_open(users=[ADMIN_USER_ID])
        if admin_dm["ok"]:
            client.chat_postMessage(
                channel=admin_dm["channel"]["id"],
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"New Questionnaire Response from {user_name}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": formatted_responses
                        }
                    }
                ]
            )
        
        # Clear user state
        del user_states[user_id]
        
    except Exception as e:
        print(f"Error sending completion messages: {e}")

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
        
        # Schedule questionnaire for later
        delay_minutes = 1 if os.environ.get("TEST_MODE", "false").lower() == "true" else 24 * 60
        scheduler.add_job(
            send_questionnaire_start,
            'date',
            run_date=datetime.now() + timedelta(minutes=delay_minutes),
            args=[client, user_id]
        )
        
    except Exception as e:
        print(f"Error in team_join handler: {e}")

# Add a test command to manually trigger messages
@app.command("/test-messages")
def test_messages(ack, command, client):
    """Test command to send both welcome and follow-up messages"""
    ack()
    user_id = command['user_id']
    
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
    send_questionnaire_start(client, user_id)
    
    # Respond in the channel where command was issued
    client.chat_postMessage(
        channel=command['channel_id'],
        text="Test messages initiated! You'll receive the welcome message and questionnaire now."
    )

# Start the app with Socket Mode
if __name__ == "__main__":
    handler = SocketModeHandler(
        app=app,
        app_token=os.environ.get("SLACK_APP_TOKEN")
    )
    handler.start()