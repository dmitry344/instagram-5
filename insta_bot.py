# pip install selenium
import os
import pickle
import logging
import zipfile
from math import ceil
from random import gauss
from time import sleep as original_sleep
from xpath_compile import xpath

from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import MoveTargetOutOfBoundsException

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.by import By


def create_driver(driver_location,
				  logger,
				  proxy,
				  headless=False,
				  disable_image_load=False):
	browser = None
	err_msg = ''
	page_delay = 7
	capabilities = DesiredCapabilities.CHROME
	capabilities["pageLoadStrategy"] = "normal"
	capabilities["javascriptEnabled"] = True
	chrome_options = Options()
	chrome_options.add_argument('--mute-audio')
	chrome_options.add_argument('--dns-prefetch-disable')
	chrome_options.add_argument('--lang=en-US')
	chrome_options.add_argument('--disable-setuid-sandbox')

	if headless:
		chrome_options.add_argument("--headless")
		chrome_options.add_argument('--no-sandbox')
		user_agent = "Chrome"
		chrome_options.add_argument('user-agent={user_agent}'.format(user_agent=user_agent))
	# Proxy for chrome
	if proxy:
		if headless:
			chrome_options.add_argument(
				'--proxy-server=http://{}'.format(proxy))
		else:
			proxy_chrome_extension = create_proxy_extension(proxy)
			# add proxy extension
			if proxy_chrome_extension:
				chrome_options.add_extension(proxy_chrome_extension)

	chrome_prefs = {
		'intl.accept_languages': 'en-US',
	}

	if disable_image_load:
		chrome_prefs['profile.managed_default_content_settings.images'] = 2
	chrome_options.add_experimental_option('prefs', chrome_prefs)
	executable_path = driver_location
	try:
		browser = webdriver.Chrome(
			desired_capabilities=capabilities,
			chrome_options=chrome_options,
			executable_path=executable_path)
	except WebDriverException as exc:
		# logger.exception(exc.msg)
		highlight_print('browser', exc.msg, "initialization", "critical", logger)
		err_msg = 'Make sure chromedriver is installed at {}'.format(
			executable_path)
		return browser, err_msg
	# browser.implicitly_wait(page_delay)
	message = "Driver created!"
	highlight_print('browser', message, "initialization", "info", logger)
	print('')
	return browser, err_msg


def create_logger(log_location, username, show_logs=True):
	if username == '' or username is None:
		username = 'anonymous'
	logger = logging.getLogger(username)
	logger.setLevel(logging.DEBUG)

	logfolder = get_logfolder(username, True, log_location)
	if not os.path.exists(logfolder):
		os.makedirs(logfolder)
	file_handler = logging.FileHandler('{}general.log'.format(logfolder))
	# file_handler.setLevel(logging.DEBUG)
	extra = {"username": username}
	logger_formatter = logging.Formatter(
		'%(levelname)s [%(asctime)s] [%(username)s]  %(message)s',
		datefmt='%Y-%m-%d %H:%M:%S')
	file_handler.setFormatter(logger_formatter)
	logger.addHandler(file_handler)
	if show_logs is True:
		console_handler = logging.StreamHandler()
		console_handler.setLevel(logging.DEBUG)
		console_handler.setFormatter(logger_formatter)
		logger.addHandler(console_handler)
	logger = logging.LoggerAdapter(logger, extra)
	return logger


def login_user(browser,
			   username,
			   password,
			   logger,
			   log_location,
			   bypass_suspicious_attempt=False,
			   bypass_with_mobile=False):
	"""Logins the user with the given username and password"""
	assert username, 'Username not provided'
	assert password, 'Password not provided'

	login_submit_result_msg = ''
	ig_homepage = "https://www.instagram.com"
	web_address_navigator(browser, ig_homepage)
	logfolder = get_logfolder(username, True, log_location)
	cookie_loaded = False
	cookie_file = '{0}{1}_cookie.pkl'.format(logfolder, username)
	# try to load cookie from username
	try:
		for cookie in pickle.load(open(cookie_file, 'rb')):
			browser.add_cookie(cookie)
			cookie_loaded = True
	except (WebDriverException, OSError, IOError):
		print("Cookie file not found, creating cookie...")

	# force refresh after cookie load or check_authorization() will FAIL
	reload_webpage(browser)

	# wait until page fully load
	explicit_wait(browser, "PFL", [], logger, 5)
	# cookie has been LOADED, so the user SHOULD be logged in
	# check if the user IS logged in
	login_state = check_authorization(browser,
									  username,
									  "activity counts",
									  logger,
									  False)
	if login_state is True:
		dismiss_notification_offer(browser, logger)
		return True, login_submit_result_msg

	# if user is still not logged in, then there is an issue with the cookie
	# so go create a new cookie..
	if cookie_loaded:
		print("Issue with cookie for user {}. Creating "
			  "new cookie...".format(username))

	# Check if the first div is 'Create an Account' or 'Log In'
	try:
		login_elem = browser.find_element_by_xpath(
			read_xpath(login_user.__name__, "login_elem"))
	except NoSuchElementException:
		print("Login A/B test detected! Trying another string...")
		try:
			login_elem = browser.find_element_by_xpath(
				read_xpath(login_user.__name__, "login_elem_no_such_exception"))
		except NoSuchElementException:
			login_submit_result_msg = "We couldn't connect to Instagram. Make sure you're connected to the internet " \
									  "and try again. Otherwise, check your proxy address."
			return False, login_submit_result_msg

	if login_elem is not None:
		try:
			(ActionChains(browser)
			 .move_to_element(login_elem)
			 .click()
			 .perform())
		except MoveTargetOutOfBoundsException:
			login_elem.click()

	# wait until it navigates to the login page
	login_page_title = "Login"
	explicit_wait(browser, "TC", login_page_title, logger)

	# wait until the 'username' input element is located and visible
	input_username_XP = read_xpath(login_user.__name__, "input_username_XP")
	explicit_wait(browser, "VOEL", [input_username_XP, "XPath"], logger)

	input_username = browser.find_element_by_xpath(input_username_XP)

	(ActionChains(browser)
	 .move_to_element(input_username)
	 .click()
	 .send_keys(username)
	 .perform())

	sleep(1)

	#  password
	input_password = browser.find_elements_by_xpath(
		read_xpath(login_user.__name__, "input_password"))

	if not isinstance(password, str):
		password = str(password)

	(ActionChains(browser)
	 .move_to_element(input_password[0])
	 .click()
	 .send_keys(password)
	 .perform())

	sleep(1)

	(ActionChains(browser)
	 .move_to_element(input_password[0])
	 .click()
	 .send_keys(Keys.ENTER)
	 .perform())

	# wait until page fully load
	explicit_wait(browser, "PFL", [], logger, 5)

	login_state = check_authorization(browser,
									  username,
									  "activity counts",
									  logger,
									  False)
	if login_state is True:
		# dismiss_get_app_offer(browser, logger)    # when try to log in with mobile
		dismiss_notification_offer(browser, logger)
		if bypass_suspicious_attempt is True:
			bypass_suspicious_login(browser, bypass_with_mobile)

		# create cookie for username
		pickle.dump(browser.get_cookies(), open(cookie_file, 'wb'))
		print('Cookie for username saved.')
		return True, login_submit_result_msg

	else:
		# To get failed reason, check if P tag id='slfErrorAlert' exists and then get its value
		login_submit_result = browser.find_elements_by_xpath(
			read_xpath(login_user.__name__, 'login_submit_result'))
		if login_submit_result:
			login_submit_result_msg = login_submit_result[0].text.replace('\n', '')
			return False, login_submit_result_msg
		else:
			login_submit_result_msg = 'unknown login error'
			return False, login_submit_result_msg


def bypass_suspicious_login(browser, bypass_with_mobile):
	"""Bypass suspicious loggin attempt verification. This should be only
    enabled
    when there isn't available cookie for the username, otherwise it will and
    shows "Unable to locate email or phone button" message, folollowed by
    CRITICAL - Wrong login data!"""
	# close sign up Instagram modal if available
	try:
		close_button = browser.find_element_by_xpath(read_xpath(bypass_suspicious_login.__name__, "close_button"))

		(ActionChains(browser)
		 .move_to_element(close_button)
		 .click()
		 .perform())


	except NoSuchElementException:
		pass

	try:
		# click on "This was me" button if challenge page was called
		this_was_me_button = browser.find_element_by_xpath(
			read_xpath(bypass_suspicious_login.__name__, "this_was_me_button"))

		(ActionChains(browser)
		 .move_to_element(this_was_me_button)
		 .click()
		 .perform())

	except NoSuchElementException:
		# no verification needed
		pass

	try:
		choice = browser.find_element_by_xpath(
			read_xpath(bypass_suspicious_login.__name__, "choice")).text

	except NoSuchElementException:
		try:
			choice = browser.find_element_by_xpath(
				read_xpath(bypass_suspicious_login.__name__, "choice_no_such_element")).text

		except Exception:
			try:
				choice = browser.find_element_by_xpath(
					read_xpath(bypass_suspicious_login.__name__, "choice_exception")).text

			except Exception:
				print("Unable to locate email or phone button, maybe "
					  "bypass_suspicious_login=True isn't needed anymore.")
				return False

	if bypass_with_mobile:
		choice = browser.find_element_by_xpath(
			read_xpath(bypass_suspicious_login.__name__, "bypass_with_mobile_choice")).text

		mobile_button = browser.find_element_by_xpath(
			read_xpath(bypass_suspicious_login.__name__, "bypass_with_mobile_button"))

		(ActionChains(browser)
		 .move_to_element(mobile_button)
		 .click()
		 .perform())

		sleep(5)

	send_security_code_button = browser.find_element_by_xpath(
		read_xpath(bypass_suspicious_login.__name__, "send_security_code_button"))

	(ActionChains(browser)
	 .move_to_element(send_security_code_button)
	 .click()
	 .perform())

	print('Instagram detected an unusual login attempt')
	print('A security code was sent to your {}'.format(choice))
	security_code = input('Type the security code here: ')

	security_code_field = browser.find_element_by_xpath((
		read_xpath(bypass_suspicious_login.__name__, "security_code_field")))

	(ActionChains(browser)
	 .move_to_element(security_code_field)
	 .click()
	 .send_keys(security_code)
	 .perform())

	submit_security_code_button = browser.find_element_by_xpath(
		read_xpath(bypass_suspicious_login.__name__, "submit_security_code_button"))

	(ActionChains(browser)
	 .move_to_element(submit_security_code_button)
	 .click()
	 .perform())

	try:
		sleep(5)
		# locate wrong security code message
		wrong_login = browser.find_element_by_xpath((
			read_xpath(bypass_suspicious_login.__name__, "wrong_login")))

		if wrong_login is not None:
			print(('Wrong security code! Please check the code Instagram'
				   'sent you and try again.'))

	except NoSuchElementException:
		# correct security code
		pass


def dismiss_get_app_offer(browser, logger):
	""" Dismiss 'Get the Instagram App' page after a fresh login """
	offer_elem = read_xpath(dismiss_get_app_offer.__name__, "offer_elem")
	dismiss_elem = read_xpath(dismiss_get_app_offer.__name__, "dismiss_elem")

	# wait a bit and see if the 'Get App' offer rises up
	offer_loaded = explicit_wait(
		browser, "VOEL", [offer_elem, "XPath"], logger, 5, False)

	if offer_loaded:
		dismiss_elem = browser.find_element_by_xpath(dismiss_elem)
		click_element(browser, dismiss_elem)


def dismiss_notification_offer(browser, logger):
	""" Dismiss 'Turn on Notifications' offer  """
	offer_elem_loc = read_xpath(dismiss_notification_offer.__name__, "offer_elem_loc")
	dismiss_elem_loc = read_xpath(dismiss_notification_offer.__name__, "dismiss_elem_loc")

	# wait a bit and see if the 'Turn on Notifications' offer rises up
	offer_loaded = explicit_wait(
		browser, "VOEL", [offer_elem_loc, "XPath"], logger, 4, False)

	if offer_loaded:
		dismiss_elem = browser.find_element_by_xpath(dismiss_elem_loc)
		click_element(browser, dismiss_elem)


def click_element(browser, element, tryNum=0):
	"""
    There are three (maybe more) different ways to "click" an element/button.
    1. element.click()
    2. element.send_keys("\n")
    3. browser.execute_script("document.getElementsByClassName('" +
    element.get_attribute("class") + "')[0].click()")

    I'm guessing all three have their advantages/disadvantages
    Before committing over this code, you MUST justify your change
    and potentially adding an 'if' statement that applies to your
    specific case. See the following issue for more details
    https://github.com/timgrossmann/InstaPy/issues/1232

    explaination of the following recursive function:
      we will attempt to click the element given, if an error is thrown
      we know something is wrong (element not in view, element doesn't
      exist, ...). on each attempt try and move the screen around in
      various ways. if all else fails, programmically click the button
      using `execute_script` in the browser.
      """

	try:
		# use Selenium's built in click function
		element.click()

	except Exception:
		# click attempt failed
		# try something funky and try again

		if tryNum == 0:
			# try scrolling the element into view
			browser.execute_script(
				"document.getElementsByClassName('" + element.get_attribute(
					"class") + "')[0].scrollIntoView({ inline: 'center' });")

		elif tryNum == 1:
			# well, that didn't work, try scrolling to the top and then
			# clicking again
			browser.execute_script("window.scrollTo(0,0);")

		elif tryNum == 2:
			# that didn't work either, try scrolling to the bottom and then
			# clicking again
			browser.execute_script(
				"window.scrollTo(0,document.body.scrollHeight);")

		else:
			# try `execute_script` as a last resort
			# print("attempting last ditch effort for click, `execute_script`")
			browser.execute_script(
				"document.getElementsByClassName('" + element.get_attribute(
					"class") + "')[0].click()")
			# update server calls after last click attempt by JS
			# update_activity()
			# end condition for the recursive function
			return

		# sleep for 1 second to allow window to adjust (may or may not be
		# needed)
		sleep_actual(1)

		tryNum += 1

		# try again!
		click_element(browser, element, tryNum)


def explicit_wait(browser, track, ec_params, logger, timeout=35, notify=True):
	"""
    Explicitly wait until expected condition validates

    :param browser: webdriver instance
    :param track: short name of the expected condition
    :param ec_params: expected condition specific parameters - [param1, param2]
    :param logger: the logger instance
    """
	# list of available tracks:
	# <https://seleniumhq.github.io/selenium/docs/api/py/webdriver_support/
	# selenium.webdriver.support.expected_conditions.html>

	if not isinstance(ec_params, list):
		ec_params = [ec_params]

	# find condition according to the tracks
	if track == "VOEL":
		elem_address, find_method = ec_params
		ec_name = "visibility of element located"

		find_by = (By.XPATH if find_method == "XPath" else
				   By.CSS_SELECTOR if find_method == "CSS" else
				   By.CLASS_NAME)
		locator = (find_by, elem_address)
		condition = ec.visibility_of_element_located(locator)

	elif track == "TC":
		expect_in_title = ec_params[0]
		ec_name = "title contains '{}' string".format(expect_in_title)

		condition = ec.title_contains(expect_in_title)

	elif track == "PFL":
		ec_name = "page fully loaded"
		condition = (lambda browser: browser.execute_script("return document.readyState") in ["complete" or "loaded"])

	elif track == "SO":
		ec_name = "staleness of"
		element = ec_params[0]

		condition = ec.staleness_of(element)

	# generic wait block
	try:
		wait = WebDriverWait(browser, timeout)
		result = wait.until(condition)

	except TimeoutException:
		if notify is True:
			logger.info(
				"Timed out with failure while explicitly waiting until {}!\n"
					.format(ec_name))
		return False

	return result


def check_authorization(browser, username, method, logger, notify=True):
	""" Check if user is NOW logged in """
	if notify is True:
		logger.info("Checking if '{}' is logged in...".format(username))

	# different methods can be added in future
	if method == "activity counts":

		# navigate to owner's profile page only if it is on an unusual page
		current_url = get_current_url(browser)
		if (not current_url or
				"https://www.instagram.com" not in current_url or
				"https://www.instagram.com/graphql/" in current_url):
			profile_link = 'https://www.instagram.com/{}/'.format(username)
			web_address_navigator(browser, profile_link)

		# if user is not logged in, `activity_counts` will be `None`- JS `null`
		try:
			activity_counts = browser.execute_script(
				"return window._sharedData.activity_counts")

		except WebDriverException:
			try:
				browser.execute_script("location.reload()")
				activity_counts = browser.execute_script(
					"return window._sharedData.activity_counts")

			except WebDriverException:
				activity_counts = None

		# if user is not logged in, `activity_counts_new` will be `None`- JS
		# `null`
		try:
			activity_counts_new = browser.execute_script(
				"return window._sharedData.config.viewer")

		except WebDriverException:
			try:
				browser.execute_script("location.reload()")
				activity_counts_new = browser.execute_script(
					"return window._sharedData.config.viewer")

			except WebDriverException:
				activity_counts_new = None

		if activity_counts is None and activity_counts_new is None:
			if notify is True:
				logger.critical(
					"--> '{}' is not logged in!\n".format(username))
			return False

	return True


def reload_webpage(browser):
	""" Reload the current webpage """
	browser.execute_script("location.reload()")
	sleep(2)

	return True


def web_address_navigator(browser, link):
	"""Checks and compares current URL of web page and the URL to be
    navigated and if it is different, it does navigate"""
	current_url = get_current_url(browser)
	total_timeouts = 0
	page_type = None  # file or directory

	# remove slashes at the end to compare efficiently
	if current_url is not None and current_url.endswith('/'):
		current_url = current_url[:-1]

	if link.endswith('/'):
		link = link[:-1]
		page_type = "dir"  # slash at the end is a directory

	new_navigation = (current_url != link)

	if current_url is None or new_navigation:
		link = link + '/' if page_type == "dir" else link  # directory links
		# navigate faster

		while True:
			try:
				browser.get(link)
				sleep(2)
				break

			except TimeoutException as exc:
				if total_timeouts >= 7:
					raise TimeoutException(
						"Retried {} times to GET '{}' webpage "
						"but failed out of a timeout!\n\t{}".format(
							total_timeouts,
							str(link).encode("utf-8"),
							str(exc).encode("utf-8")))
				total_timeouts += 1
				sleep(2)


def sleep(t, custom_percentage=None):
	sleep_percentage = 1
	if custom_percentage is None:
		custom_percentage = sleep_percentage
	time = randomize_time(t) * custom_percentage
	original_sleep(time)


def sleep_actual(t):
	original_sleep(t)


def randomize_time(mean):
	# i.e. random time will be in the range: TIME +/- STDEV %
	STDEV = 0.5
	allowed_range = mean * STDEV
	stdev = allowed_range / 3  # 99.73% chance to be in the allowed range

	t = 0
	while abs(mean - t) > allowed_range:
		t = gauss(mean, stdev)

	return t


def get_current_url(browser):
	""" Get URL of the loaded webpage """
	try:
		current_url = browser.execute_script("return window.location.href")

	except WebDriverException:
		try:
			current_url = browser.current_url

		except WebDriverException:
			current_url = None

	return current_url


def highlight_print(username=None, message=None, priority=None, level=None,
					logger=None):
	""" Print headers in a highlighted style """
	# can add other highlighters at other priorities enriching this function

	# find the number of chars needed off the length of the logger message
	output_len = (28 + len(username) + 3 + len(message) if logger
				  else len(message))
	show_logs = True

	if priority in ["initialization", "end"]:
		# OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
		# E.g.:          Driver started!
		# oooooooooooooooooooooooooooooooooooooooooooooooo
		upper_char = "O"
		lower_char = "o"

	elif priority == "login":
		# ................................................
		# E.g.:        Logged in successfully!
		# ''''''''''''''''''''''''''''''''''''''''''''''''
		upper_char = "."
		lower_char = "'"

	elif priority == "feature":  # feature highlighter
		# ________________________________________________
		# E.g.:    Starting to interact by users..
		# """"""""""""""""""""""""""""""""""""""""""""""""
		upper_char = "_"
		lower_char = "\""

	elif priority == "user iteration":
		# ::::::::::::::::::::::::::::::::::::::::::::::::
		# E.g.:            User: [1/4]
		upper_char = ":"
		lower_char = None

	elif priority == "post iteration":
		# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		# E.g.:            Post: [2/10]
		upper_char = "~"
		lower_char = None

	elif priority == "workspace":
		# ._. ._. ._. ._. ._. ._. ._. ._. ._. ._. ._. ._.
		upper_char = " ._. "
		lower_char = None

	if (upper_char
			and (show_logs
				 or priority == "workspace")):
		print("\n{}".format(
			upper_char * int(ceil(output_len / len(upper_char)))))

	if level == "info":
		if logger:
			logger.info(message)
		else:
			print(message)

	elif level == "warning":
		if logger:
			logger.warning(message)
		else:
			print(message)

	elif level == "critical":
		if logger:
			logger.critical(message)
		else:
			print(message)

	if (lower_char
			and (show_logs
				 or priority == "workspace")):
		print("{}".format(
			lower_char * int(ceil(output_len / len(lower_char)))))


def get_logfolder(username, multi_logs, log_location):
	if multi_logs:
		logfolder = "{0}{1}{2}{1}".format(log_location,
										  os.path.sep,
										  username)
	else:
		logfolder = (log_location + os.path.sep)

	validate_path(logfolder)
	return logfolder


def validate_path(path):
	""" Make sure the given path exists """

	if not os.path.exists(path):
		try:
			os.makedirs(path)

		except OSError as exc:
			exc_name = type(exc).__name__
			msg = ("{} occured while making \"{}\" path!"
				   "\n\t{}".format(exc_name,
								   path,
								   str(exc).encode("utf-8")))


def read_xpath(function_name, xpath_name):
	return xpath[function_name][xpath_name]


def create_proxy_extension(proxy):
	""" takes proxy looks like login:password@ip:port """
	if '@' in proxy:
		ip = proxy.split('@')[1].split(':')[0]
		port = int(proxy.split(':')[-1])
		login = proxy.split(':')[0]
		password = proxy.split(':')[1]
	else:
		ip = proxy.split(':')[0]
		port = int(proxy.split(':')[-1])
		login = ''
		password = ''

	manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version":"22.0.0"
        }
    """

	background_js = """
        var config = {
                mode: "fixed_servers",
                rules: {
                  singleProxy: {
                    scheme: "http",
                    host: "%s",
                    port: parseInt(%s)
                  },
                  bypassList: ["localhost"]
                }
              };
        chrome.proxy.settings.set({value: config, scope: "regular"}, 
        function() {});
        function callbackFn(details) {
            return {
                authCredentials: {
                    username: "%s",
                    password: "%s"
                }
            };
        }
        chrome.webRequest.onAuthRequired.addListener(
                    callbackFn,
                    {urls: ["<all_urls>"]},
                    ['blocking']
        );
    """ % (ip, port, login, password)

	dir_path = 'assets/chrome_extensions'

	if not os.path.exists(dir_path):
		os.makedirs(dir_path)

	pluginfile = '%s/proxy_auth_%s:%s.zip' % (dir_path, ip, port)
	with zipfile.ZipFile(pluginfile, 'w') as zp:
		zp.writestr("manifest.json", manifest_json)
		zp.writestr("background.js", background_js)

	return pluginfile
