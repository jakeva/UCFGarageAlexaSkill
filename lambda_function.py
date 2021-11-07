import requests
from bs4 import BeautifulSoup

import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration
import logging

import ask_sdk_core.utils as ask_utils
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

sentry_sdk.init(dsn="SENTRY_KEY", integrations=[AwsLambdaIntegration()])

# function to parse and get all garage data and input it all into one dictionary
def get_garage_data():
    page = requests.get('https://secure.parking.ucf.edu/GarageCount/').content
    soup = BeautifulSoup(page, 'html.parser')  # turn the site into a BeautifulSoup object

    all_tables = soup.find_all('table')  # find all tables in page (only returns 1 anyway, but this is to future proof)
    garages_table = None

    for table in all_tables:
        if 'garage' in table.text.lower():  # make sure the table is talking about garages
            garages_table = table  # assign this table to garages_table
            break

    if garages_table is None:
        print('\nError: table not found.')  # throw error

    garages_data = {}  # create empty dictionary
    garage_rows = garages_table.find_all('tr')[5:-1]  # find table rows 2-one before end and store in garage_rows

    # sort through all rows and extract data
    for row in garage_rows:
        row_data = row.find_all('td')
        garage_name = row_data[0].text.strip().replace('Garage ', '').upper()  # remove 'garage' from the actual garage name

        percent_full_text = row_data[2].text.strip()
        percent_full_index = percent_full_text.find('percent: ') + len('percent:')
        percent_full_end = percent_full_text[percent_full_index - 1:].find(',') + percent_full_index

        percent_full = percent_full_text[percent_full_index:percent_full_end]

        percentage = percent_full.replace(',', '').replace(' ', '')  # remove comma and uneccessary space

        # check if percentage is out of bounds
        if int(percentage) < 0:
            percentage = '0'
        elif int(percentage) > 100:
            percentage = '100'

        garages_data[garage_name] = percentage
    return garages_data

# function to get specific garage data
def get_specific_garage_data(name):
    data = get_garage_data()
    return data[name]


# function to get all garage data
def get_all_garage_data_as_string():
    dictionary = get_garage_data()

    garage_list = ''
    for key in dictionary.keys():
        if key != 'LIBRA':
            garage_list += 'Garage ' + key.capitalize() + ' is at ' + dictionary[key] + ' percent capacity, '
        else:
            garage_list += 'and ' + key.capitalize() + ' Garage is at ' + dictionary[key] + ' percent capacity.'

    return garage_list

# function to get the lowest percentage and the according garage name
def get_lowest_percentage():
    empty_garages = []

    garages_data = get_garage_data()

    sorted_garages_data = sorted((int(value), key) for (key, value) in garages_data.items())  # sort them

    minimum_percentage = sorted_garages_data[0][0]  # find the minimum percentage

    # loop through and append the garages with fullness == minimum
    for percentage, garage_name in sorted_garages_data:
        if percentage > minimum_percentage:
            break
        else:
            empty_garages.append((garage_name, percentage))

    # build a string response out of this list
    string_response = ''

    empties_length = len(empty_garages)

    if empties_length == 1:
        string_response = 'Garage %s is the least full with %d percent capacity.' % (empty_garages[0][0], empty_garages[0][1])
    elif empties_length == 2:
        string_response = 'Garages %s and %s are the least full with %d percent capacity.' % (empty_garages[0][0], empty_garages[1][0], empty_garages[0][1])
    elif 3 <= empties_length < len(garages_data):
        string_response = 'Garages '

        for i in range(empties_length - 1):
            string_response += '%s, ' % empty_garages[i][0]

        string_response += 'and %s' % empty_garages[-1][0]

        string_response += ' are the least full with %d percent capacity.' % empty_garages[-1][1]
    else:
        string_response = 'All garages are %d percent full.' % empty_garages[-1][1]

    return string_response

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Welcome to the UCF Garage Availability skill. For help, say help."

        return handler_input.response_builder.speak(speak_output).ask(speak_output).response


class SpecificGarageIntentHandler(AbstractRequestHandler):
    """Handler for Specific Garage Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("SpecificGarageIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        speak_output = ''
        garage_name = handler_input.request_envelope.request.intent.slots['garage_name'].value
        try:
            percentage = get_specific_garage_data(garage_name.replace('.', '').upper())

            if garage_name.replace('.', '') != 'LIBRA':
                speak_output = 'Garage ' + garage_name.capitalize().replace('.', '') + ' is at ' + percentage + ' percent capacity.'
            else:
                speak_output = garage_name.capitalize().replace('.', '') + ' Garage is at ' + percentage + ' percent capacity.'
        except KeyError:
            speak_output = 'Garage ' + garage_name + ' either does not exist or is not available to see how full it is.'

        return handler_input.response_builder.speak(speak_output).ask("If you want to ask another question, let me know. Otherwise, say stop.").response

class AllGarageIntentHandler(AbstractRequestHandler):
    """Handler for All Garage Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AllGarageIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        speak_output = get_all_garage_data_as_string()

        return handler_input.response_builder.speak(speak_output).ask("If you want to ask another question, let me know. Otherwise, say stop.").response

class EmptiestGarageIntentHandler(AbstractRequestHandler):
    """Handler for Emptiest Garage Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("EmptiestGarageIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        speak_output = get_lowest_percentage()

        return handler_input.response_builder.speak(speak_output).ask("If you want to ask another question, let me know. Otherwise, say stop.").response

class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = ("This skill tells you how full each of the garages are at UCF. "
                        "You can ask how full is garage A, B, C, D, H, I, or Libra, "
                        " how full all garages are, "
                        " or what the emptiest garage is.")

        return handler_input.response_builder.speak(speak_output).ask(speak_output).response


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Goodbye."

        return handler_input.response_builder.speak(speak_output).response


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """

    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        sentry_sdk.capture_exception(exception)
        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return handler_input.response_builder.speak(speak_output).ask(speak_output).response


# The SkillBuilder object acts as the entry point for your skill, routing all request and response payloads to the handlers above.
sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(AllGarageIntentHandler())
sb.add_request_handler(SpecificGarageIntentHandler())
sb.add_request_handler(EmptiestGarageIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
