import os
import time
import re
from slackclient import SlackClient

import wiringpi

# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
print("slack token: " + os.environ.get('SLACK_BOT_TOKEN'))
# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "position"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"


# pins
PUMP_PIN = 14

def try_parse_int(s, base=10, val=None):
  """
   do the best job possible to convert a string to an int, taking an optional
   fallback value

   s: the string to parse as an integer
   base: the integer base to use for parsing the int (TODO: unnecessary?)
   val: the value to return if the string cannot be parsed.
  """
  try:
    return int(s, base)
  except ValueError:
    return val

def try_parse_float(s, val=None):
  """
    do the best job possible to convert a float to an int, taking an optional
    fallback value

    s: the string to parse as a float
    val: the value to return if the string cannot be parsed
  try:
    return float(s)
  except ValueError:
    return val

def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == starterbot_id:
                return message, event["channel"]
    return None, None

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def setup_servo():
    """
      Set up a pin for PWM output, suitable for servo control.
      This function is currently unused by the waterbot.
    """
    # set #18 to be a PWM output
    wiringpi.pinMode(18, wiringpi.GPIO.PWM_OUTPUT)
     
    # set the PWM mode to milliseconds stype
    wiringpi.pwmSetMode(wiringpi.GPIO.PWM_MODE_MS)
     
    # divide down clock
    wiringpi.pwmSetClock(192)
    wiringpi.pwmSetRange(2000)

def setup_pump():
    # set the pump pin as output
    wiringpi.pinMode(PUMP_PIN, 1)

def pump_on():
    # just publish "hi" to the pump pin
    wiringpi.digitalWrite(PUMP_PIN, 1)

def pump_off():
    # just publish "low" to the pump pin
    wiringpi.digitalWrite(PUMP_PIN, 0)

# unused function used to test servo
# def sweep_pos():
#     delay_period = 0.01
#     for pulse in range(100, 200, 1):
#         wiringpi.pwmWrite(18, pulse)
#         time.sleep(delay_period)

# unused function used to move servo to a specific position
#def move_to_pos(pos):
#    pos = min(100, max(0, pos))
#    delay_period = 0.01
#    wiringpi.pwmWrite(18, 100 + pos)
#    return pos

def handle_command(command, channel):
    """
        Executes bot command if the command is known
    """
    # Default response is help text for the user
    default_response = "Not sure what you mean. Try *{}*.".format(EXAMPLE_COMMAND)

    # Finds and executes the given command, filling in response
    response = None
    # This is where you start to implement more commands!
    print('Received command "' + command + '"')

    # this logic is really messy. TODO: rewrite the program flow.

    if command.startswith(EXAMPLE_COMMAND):
        # attempting to move the servo to a position. Look for a position to move to.
        pos = try_parse_int(command.split(" ")[1])
        if pos is not None:
            pos = move_to_pos(pos)
       	    response = "Moved to position " + str(pos)
        else:
            response = "Couldn't parse input. Must provide integer"

    # do a position sweep on the servo
    elif command.startswith("sweep"):
        sweep_pos()
        response = "Did a position sweep"

    # water for the appropriate amount of time
    elif command.startswith("water"):
        # check if no time is given, and in that case water for 10s
	if len(command.split(" ")) == 1:
            secs = 10
        # if something comes after, try to read it as a length of time to water
        else:
            secs = try_parse_float(command.split(" ")[1])
            if secs is None:
                # not a number
                response = 'Couldn\'t parse your input (try "water 5")'
            elif secs <= 0 or secs > 30:
                # so some choog doesn't water all the water and burn out the pump
                response = 'I can\'t water for that long. Try a number between 0 and 30'
                secs = None
            if secs is not None:
                # an appropriate, numerical amount of seconds to water :)
	        water(secs)
	        response = "Watered for " + str(secs) + " seconds"

    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
    )

def water(secs):
    pump_on()
    time.sleep(secs)
    pump_off()

if __name__ == "__main__":
    # required to use wiringpi later
    wiringpi.wiringPiSetupGpio()
    # setup_servo()
    setup_pump()
    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
