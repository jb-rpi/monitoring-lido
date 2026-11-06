
import os
import requests
import json
import time

# Configuration from environment variables
BEACON_NODE_URL = os.getenv("BEACON_NODE_URL", "http://localhost:5052")
VALIDATOR_ID = os.getenv("VALIDATOR_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
SLOTS_PER_EPOCH = 32
MAX_EFFECTIVE_BALANCE_GWEI = 32_000_000_000

# Path for storing last known status (in the temporary directory)
STATUS_FILE = os.path.join(os.getenv("GEMINI_TMP_DIR", "/tmp"), "validator_status.json")

def read_last_status():
    """Reads the last known validator status from a file."""
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"is_online": True, "last_message_sent": None} # Default to online if file is corrupt
    return {"is_online": True, "last_message_sent": None} # Default to online if no file

def write_current_status(is_online, last_message_sent, balance=None, epoch=None):
    """Writes the current validator status to a file."""
    with open(STATUS_FILE, 'w') as f:
        json.dump({"is_online": is_online, "last_message_sent": last_message_sent, "balance": balance, "epoch": epoch}, f)

def send_discord_message(message_content, webhook_url):
    """Sends a message to a Discord webhook."""
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK_URL is not set. Cannot send Discord message.")
        return False
    
    headers = {'Content-Type': 'application/json'}
    payload = {'content': message_content}
    
    try:
        response = requests.post(webhook_url, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status()
        print(f"Discord message sent: {message_content}")
        return True
    except requests.exceptions.Timeout:
        print("Error: Sending Discord message timed out.")
        return False
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to Discord webhook URL.")
        return False
    except requests.exceptions.HTTPError as http_err:
        print(f"Error sending Discord message: {http_err} - Status: {response.status_code} - Response: {response.text}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while sending Discord message: {e}")
        return False

def check_validator_status(validator_id, beacon_node_url):
    """
    Fetches the status of a Lighthouse validator from the Beacon Node API.
    Returns True if the validator is active_ongoing and the node is reachable, False otherwise.
    """
    if not validator_id:
        print("Error: VALIDATOR_ID environment variable is not set.")
        return False, "VALIDATOR_ID not set"
    if not beacon_node_url:
        print("Error: BEACON_NODE_URL environment variable is not set.")
        return False, "BEACON_NODE_URL not set"

    endpoint = f"/eth/v1/beacon/states/head/validators/{validator_id}"
    url = f"{beacon_node_url}{endpoint}"

    try:
        response = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data and 'data' in data:
            validator_data = data['data']
            status = validator_data.get('status')
            print(f"Validator {validator_id} status: {status}")
            if status == "active_ongoing":
                return True, "active_ongoing"
            else:
                return False, f"Validator status is '{status}' (not active_ongoing)"
        else:
            return False, "No data or 'data' key missing in validator status response."

    except requests.exceptions.Timeout:
        return False, f"Connection to Beacon Node {beacon_node_url} timed out."
    except requests.exceptions.ConnectionError:
        return False, f"Could not connect to Lighthouse Beacon Node at {beacon_node_url}. Is it running?"
    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 404:
            return False, f"Error 404: Validator with ID '{validator_id}' not found or invalid endpoint. Check VALIDATOR_ID."
        else:
            return False, f"HTTP error occurred: {http_err} - Status: {response.status_code} - Response: {response.text}"
    except json.JSONDecodeError:
        return False, f"Error: Could not decode JSON response from {url}"
    except Exception as e:
        return False, f"An unexpected error occurred during status check: {e}"

def check_performance(validator_id, beacon_node_url, last_status):
    """
    Checks slashing, balance trend and attestation liveness.
    Returns (ok, reason, balance, epoch).
    """
    try:
        r = requests.get(f"{beacon_node_url}/eth/v1/beacon/states/head/validators/{validator_id}", timeout=10)
        r.raise_for_status()
        data = r.json()["data"]
        index = data["index"]
        balance = int(data["balance"])
        slashed = data["validator"]["slashed"]

        r = requests.get(f"{beacon_node_url}/eth/v1/beacon/headers/head", timeout=10)
        r.raise_for_status()
        epoch = int(r.json()["data"]["header"]["message"]["slot"]) // SLOTS_PER_EPOCH

        r = requests.post(f"{beacon_node_url}/eth/v1/validator/liveness/{epoch - 1}", json=[str(index)], timeout=10)
        r.raise_for_status()
        is_live = any(str(e["index"]) == str(index) and e["is_live"] for e in r.json()["data"])
    except Exception as e:
        return False, f"Performance check failed: {e}", last_status.get("balance"), last_status.get("epoch")

    problems = []
    if slashed:
        problems.append("validator is SLASHED")
    last_balance, last_epoch = last_status.get("balance"), last_status.get("epoch")
    swept = balance == MAX_EFFECTIVE_BALANCE_GWEI and last_balance is not None and last_balance > MAX_EFFECTIVE_BALANCE_GWEI
    if last_balance is not None and last_epoch is not None and epoch > last_epoch and balance < last_balance and not swept:
        problems.append(f"balance decreased {last_balance} -> {balance} gwei")
    if not is_live:
        problems.append(f"no attestation seen in epoch {epoch - 1}")

    print(f"Validator {validator_id} balance: {balance} gwei, epoch: {epoch}, live: {is_live}")
    return not problems, "; ".join(problems) or "active_ongoing", balance, epoch

def main():
    print(f"Starting validator monitoring for {VALIDATOR_ID}...")

    current_state_online, reason = check_validator_status(VALIDATOR_ID, BEACON_NODE_URL)
    last_status = read_last_status()
    was_online = last_status.get("is_online", True) # Default to True if not found
    balance, epoch = last_status.get("balance"), last_status.get("epoch")
    if current_state_online:
        current_state_online, reason, balance, epoch = check_performance(VALIDATOR_ID, BEACON_NODE_URL, last_status)

    if current_state_online and not was_online:
        message = f"✅ Validator {VALIDATOR_ID} is back ONLINE. ({reason})"
        print(message)
        send_discord_message(message, DISCORD_WEBHOOK_URL)
        write_current_status(True, message, balance, epoch)
    elif not current_state_online and was_online:
        message = f"🚨 Validator {VALIDATOR_ID} is OFFLINE! ({reason})"
        print(message)
        send_discord_message(message, DISCORD_WEBHOOK_URL)
        write_current_status(False, message, balance, epoch)
    elif not current_state_online and not was_online:
        # Still offline, log but don't resend Discord message unless it was a different reason (optional: can add a timestamp check)
        print(f"⚠️ Validator {VALIDATOR_ID} is still OFFLINE. ({reason})")
        # To avoid spamming, we only send a new message if the previous one wasn't sent or if the reason changes significantly.
        # For simplicity here, we'll only send on state change (online -> offline or vice versa).
        # A more advanced version might resend after a long period of being offline or if the error reason changes.
        # For now, just update the reason in the status file.
        write_current_status(False, reason, balance, epoch) # Update reason, but don't change 'is_online' if it's already False
    else:
        print(f"✅ Validator {VALIDATOR_ID} is ONLINE. ({reason})")
        write_current_status(True, reason, balance, epoch)

if __name__ == "__main__":
    main()
