#wwww.BinaryAcademy.uk
#Binary Options Trading Bot with EMA Strategy
#EDITED BY BINARY ACADEMY
#This bot uses EMA strategy to trade binary options on Deriv platform.
#It uses the Deriv API to place trades based on EMA signals.
#The bot is designed to be run in a simulated environment for testing purposes.
#It is not intended for live trading without proper testing and validation.
#Please use at your own risk.
#This bot is for educational purposes only and should not be considered as financial advice.
#Join our community at www.binaryacademy.uk for more resources and support.

#For customized trading strategies and advanced features, please visit our website or contact us directly.
#

import json
import websocket
import logging
import time

# Constants
API_TOKEN = "replace_with_your_api_token"  # Replace with your Deriv API token
APP_ID = "replace_with_your_app_id"  # Replace with your Deriv app ID
SYMBOL = "replace_with_your_symbol"  # Replace with your trading symbol (e.g., "R_100")
CURRENCY = "USD"
INITIAL_STAKE = 10  # Initial stake amount (replace 10 with your desired value)
CONTRACT_TYPE = "DIGITDIFF" # Contract type for digit difference
# (e.g., "DIGITDIFF", "DIGITMATCH", etc.)
COOLDOWN_PERIOD = 10

# Variables for dynamic threshold adjustment
stake = INITIAL_STAKE  # Initial stake amount
condition_digits = 5  # Start with checking 5 identical digits
consecutive_wins = 0  # Count of consecutive wins
consecutive_losses = 0  # Count of consecutive losses
max_threshold = 6  # eg Max number of identical digits to wait for
min_threshold = 3  # eg Min number of identical digits to wait for
last_digits = []  # Track the last few digits
pending_contract_id = None  # Track the contract ID of the placed trade
checking_trade_result = False  # Whether the bot is currently checking for a trade result
simulate_next_trade = False  # Flag to control when to simulate the outcome
skip_next_opportunity = False  # Flag to skip the next trade after a real trade

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to authorize with Deriv API
def authorize(ws):
    auth_request = json.dumps({"authorize": API_TOKEN})
    ws.send(auth_request)

# Function to subscribe to real-time ticks
def subscribe_to_ticks(ws):
    tick_subscription_request = json.dumps({
        "ticks": SYMBOL,
        "subscribe": 1
    })
    ws.send(tick_subscription_request)

# Function to place a trade
def place_trade(ws, predicted_digit, duration=1):
    global pending_contract_id
    trade_request = json.dumps({
        "buy": "1",
        "price": stake,
        "parameters": {
            "amount": stake,
            "basis": "stake",
            "contract_type": CONTRACT_TYPE,
            "currency": CURRENCY,
            "symbol": SYMBOL,
            "barrier": str(predicted_digit),
            "duration": duration,
            "duration_unit": "t"
        }
    })
    ws.send(trade_request)

# Function to check trade result by contract ID
def check_trade_result(ws, contract_id):
    result_request = json.dumps({
        "proposal_open_contract": 1,
        "contract_id": contract_id
    })
    ws.send(result_request)

# Dynamic adjustment of threshold and stake after trades
def adjust_threshold():
    global condition_digits, consecutive_wins, consecutive_losses

    if consecutive_losses >= 2:
        # Increase the threshold after consecutive losses
        if condition_digits < max_threshold:
            condition_digits += 1
            logger.info(f"Increasing threshold to {condition_digits} identical digits after {consecutive_losses} consecutive losses.")
        consecutive_losses = 0  # Reset loss counter

    elif consecutive_wins >= 3:
        # Decrease the threshold after consecutive wins
        if condition_digits > min_threshold:
            condition_digits -= 1
            logger.info(f"Decreasing threshold to {condition_digits} identical digits after {consecutive_wins} consecutive wins.")
        consecutive_wins = 0  # Reset win counter

# WebSocket callback function
def on_message(ws, message):
    global pending_contract_id, checking_trade_result, stake, last_digits, consecutive_wins, consecutive_losses, simulate_next_trade, skip_next_opportunity
    data = json.loads(message)

    # Handle authorization success
    if 'authorize' in data:
        if data['authorize']:
            logger.info("Authorization successful! Subscribing to ticks...")
            subscribe_to_ticks(ws)
        else:
            logger.error("Authorization failed.")

    # Handle tick data
    elif 'tick' in data:
        tick_price = data['tick']['quote']
        last_digit = int(str(tick_price)[-1])
        last_digits.append(last_digit)

        # Keep only the last 'condition_digits' digits in memory
        if len(last_digits) > condition_digits:
            last_digits.pop(0)

        logger.info(f"Received tick: {tick_price}, Last digit: {last_digit}, Last digits: {last_digits}")

        # Simulate the outcome of a skipped trade
        if simulate_next_trade and len(last_digits) == condition_digits and len(set(last_digits)) == 1:
            simulated_outcome = "won" if last_digits[-1] % 2 == 0 else "lost"  # Simulate an arbitrary outcome
            logger.info(f"Simulated trade would have: {simulated_outcome}")

            if simulated_outcome == "won":
                logger.info("Skipping the next opportunity since the simulated trade would have won.")
                skip_next_opportunity = True  # Skip the next opportunity and simulate again
            elif simulated_outcome == "lost":
                logger.info("Placing a real trade since the simulated trade would have lost.")
                simulate_next_trade = False  # Stop simulating and place the real trade on the next opportunity
                skip_next_opportunity = False  # Reset this flag for future trades

        # Real trade condition met
        if len(last_digits) == condition_digits and len(set(last_digits)) == 1 and pending_contract_id is None and not checking_trade_result:
            predicted_digit = last_digits[-1]

            # New Filter Layer: Avoid trades when predicted digit is 1 or 9
            if predicted_digit == 1 or predicted_digit == 9:
                logger.info(f"Skipping trade as the predicted digit is {predicted_digit}.")
            else:
                logger.info(f"Condition met with {condition_digits} identical digits. Placing trade with predicted digit: {predicted_digit}")
                place_trade(ws, predicted_digit)
                simulate_next_trade = True  # Start simulating the outcome for future trades

        # If there is a pending contract, check the trade result 2 seconds after trade placement
        if pending_contract_id is not None and not checking_trade_result:
            checking_trade_result = True  # Ensure the trade result is only checked once
            logger.info("Waiting 2 seconds to check trade result...")
            time.sleep(2)  # Wait for 2 seconds before checking the trade result
            check_trade_result(ws, pending_contract_id)

    # Handle trade placement response
    elif 'buy' in data:
        pending_contract_id = data['buy']['contract_id']
        logger.info(f"Trade placed, Contract ID: {pending_contract_id}")

    # Handle contract result after the trade
    elif 'proposal_open_contract' in data:
        contract = data['proposal_open_contract']
        if contract.get('is_sold'):
            outcome = contract['status']
            profit = contract.get('profit', 0)
            logger.info(f"Trade result: {outcome}, Profit: {profit}")

            if outcome == "won":
                consecutive_wins += 1
                consecutive_losses = 0  # Reset losses on win
                logger.info(f"Trade won! Consecutive wins: {consecutive_wins}")
                stake = INITIAL_STAKE  # Reset stake after win
            else:
                consecutive_losses += 1
                consecutive_wins = 0  # Reset wins on loss
                logger.info(f"Trade lost. Consecutive losses: {consecutive_losses}")

                # Aggressive recovery strategy (multiply stake by 11)
                stake *= 11
                logger.info(f"New stake after loss: {stake}")

            pending_contract_id = None  # Clear the contract ID for the next trade
            checking_trade_result = False  # Reset trade result checking flag
            last_digits = []  # Clear stored digits
            time.sleep(COOLDOWN_PERIOD)  # Cooldown period before next trade

            # Adjust threshold dynamically based on win/loss streak
            adjust_threshold()

# WebSocket error handling
def on_error(ws, error):
    logger.error(f"WebSocket error: {error}")

# WebSocket close handling
def on_close(ws):
    logger.info("WebSocket connection closed")

# WebSocket open connection
def on_open(ws):
    authorize(ws)

# Main WebSocket logic
def run_bot():
    ws = websocket.WebSocketApp(f'wss://ws.derivws.com/websockets/v3?app_id={APP_ID}',
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()

if __name__ == "__main__":
    run_bot()
