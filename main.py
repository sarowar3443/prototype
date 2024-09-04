from flask import Flask, render_template, request, Response, jsonify, url_for, render_template_string, redirect
import requests
import subprocess
import platform
from flask_socketio import SocketIO , emit

def extract_psid(access_token):
    # URL
    url = "https://graph.facebook.com/v20.0/me/conversations"

    # Parameters
    params = {
        'fields': 'participants,messages{id,message}',
        'access_token': access_token,
        'limit': 100  # Increase the limit if you want more results per page
    }

    # Initialize an empty list to store all IDs
    psid_list = []

    while url:
        # Make the GET request
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()

            # Iterate through each conversation to get the participants
            for conversation in data.get("data", []):
                participants = conversation.get("participants", {})
                if "data" in participants and len(participants["data"]) > 0:
                    first_id = participants["data"][0]["id"]
                    psid_list.append(first_id)

            # Check if there is a next page
            url = data.get('paging', {}).get('next')

            # Clear the params after the first request
            params = {}
        else:
            print(f"Failed to retrieve data: {response.status_code}")
            print(response.json())  # Print the response content for more details
            break

    # Return the list of IDs
    return psid_list


def send_message_to_psids(psid_list, access_token):
    url = "https://graph.facebook.com/v20.0/me/messages"
    
    total_psids = len(psid_list)
    success_count = 0

    for psid in psid_list:
        # Define the parameters for each message request
        params = {
            "recipient": f'{{"id": "{psid}"}}',
            "messaging_type": "MESSAGE_TAG",
            "message": '{"text": "hello"}',
            "tag": "CONFIRMED_EVENT_UPDATE",
            "access_token": access_token
        }
        
        # Send the POST request
        response = requests.post(url, json=params)  # Use json=params for sending JSON payload
        
        # Check if the message was sent successfully
        if response.status_code == 200:
            success_count += 1

        # Emit the updated success count to the client
        socketio.emit('update_count', {'success_count': success_count, 'total_psids': total_psids})
        
    # Return summary message
    return f"Message sent to {success_count} people out of {total_psids} people."

def extract_page_id(access_token):
    # Define the URL and parameters
    url = "https://graph.facebook.com/v20.0/me"
    params = {
        'fields': 'id,name',
        'access_token': access_token
    }

    # Make the GET request
    response = requests.get(url, params=params)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        
        # Extract the page ID
        page_id = data.get('id')
        
        return page_id
    else:
        print(f"Failed to fetch data. Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
        return None
    












app = Flask(__name__)
access_token = None
recitation_ids = []
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/hello', methods=['GET', 'POST'])
def hello():
    global access_token
    if request.method == 'POST':
        data = request.get_json()
        access_token = data.get('access_token')
        return jsonify({"status": "success"})
    
    if access_token:
        page_id = extract_page_id(access_token)
        psid_list = extract_psid(access_token)
        
        # Render the template first
        rendered_template = render_template_string("""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Open Facebook Messenger</title>
                <script type="text/javascript" src="//cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
                <script type="text/javascript">
                    window.onload = function() {
                        var pageId = "{{ page_id }}";
                        var url = "https://business.facebook.com/latest/inbox/all/?nav_ref=manage_page_ap_plus_inbox_message_button&asset_id=" + pageId;
                        var windowFeatures = "width=700,height=1000,scrollbars=yes,resizable=yes";
                        window.open(url, "FacebookMessengerWindow", windowFeatures);

                        // SocketIO connection to update success count in real-time
                        var socket = io();
                        socket.on('update_count', function(data) {
                            document.getElementById('message').innerText = "Message sent to " + data.success_count + " people out of " + data.total_psids;
                        });
                    };
                </script>
            </head>
            <body>
                <p id="message">Starting message sending...</p>
            </body>
            </html>
        """, page_id=page_id)
        
        # Send the messages after rendering
        socketio.start_background_task(target=send_message_to_psids, psid_list=psid_list, access_token=access_token)
        
        return rendered_template
    else:
        return "No access token received."
if __name__ == '__main__':
    app.run(debug=True)
