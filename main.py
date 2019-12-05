from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import os
import csv
import pandas as pd
import time
from datetime import datetime
import pygsheets
from time import sleep
from urllib.request import urlretrieve
import dotenv
from pathlib import Path  # python3 only
from insta_bot import *
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

def week_of_month(dt):
    """ Returns the week of the month for the specified date.
    """

    first_day = dt.replace(day=1)

    dom = dt.day
    adjusted_dom = dom + first_day.weekday()

    return int(ceil(adjusted_dom/7.0))


def find_posts(driver, user_name):
    print("Listing posts of @{}...".format(user_name))
    driver.get("https://www.instagram.com/" + user_name)
    imgLinks = []
    c = 0
    while len(imgLinks) < 48:
        try:
            c = c + 1
            if c > 50:
                break
            if not explicit_wait(driver, "VOEL", ['.v1Nh3 a', "CSS"], logger, 5, notify=False):
                continue
            imgList = driver.find_elements_by_css_selector(".v1Nh3 a")
            for idx, img in enumerate(imgList):
                _link = img.get_property("href")
                if not _link in imgLinks:
                    imgLinks.append(_link)
            print("> " + str(len(imgLinks)) + " post collected.", "\r")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            sleep(2)

        except Exception as e1:
            print(e1)

    # print("> " + str(len(imgLinks)) + " post collected.", "\r")
    return imgLinks


# Download all pictures | return : 0 or Total_Downloaded_Photo_Number
def download_photos(driver, user_name, download_path, logger,  total_number=12):
    downloaded_number = 0
    imgLinks = find_posts(driver, user_name)
    while downloaded_number < total_number:
        for idx, link in enumerate(imgLinks):
            # Go To Link
            driver.get(link)
            # Get Photo Taken Date
            # time = driver.find_element_by_tag_name("time").get_attribute("datetime").split("T")[0] + "_"

            # If page has many photos
            try:

                img_xp = read_xpath('get_source_link', "image")
                if not explicit_wait(driver, "VOEL", [img_xp, "XPath"], logger, 5, notify=False):
                    continue
                tags = driver.find_elements_by_xpath(img_xp)

                for i in range(len(tags)):
                    img_link = tags[i].get_attribute("srcset").split(",")[0]
                    if img_link == '':
                        continue
                    img_link = img_link.split(" ")[0]
                    file_name = str(downloaded_number+1) + " " + user_name + '.jpg'
                    # Download photos

                    path = os.path.join(download_path, file_name)
                    urlretrieve(img_link, path)
                    print("> " + str(downloaded_number+1) + " / " + str(total_number) + "  downloaded...")
                    downloaded_number += 1
                    if downloaded_number == total_number:
                        print("$ Download Completed.")
                        return downloaded_number

            # If page has single photo
            except Exception as e:
                print(e)
                pass

        print("-------------------------------")


    return 0

def upload_2_google(drive, pic_user_path, tgt_folder_id):

    for r, d, f in os.walk(pic_user_path):
        for file in f:
            file_path = os.path.join(r, file)
            # with open(file_path, "r") as f:
            #     fn = os.path.basename(f.name)
            file_drive = drive.CreateFile({'title': file, "parents": [{"kind": "drive#fileLink", "id": tgt_folder_id}]})
            # f_content = f.read()
            file_drive.SetContentFile(file_path)
            file_drive.Upload()
            print("The file: " + file + " has been uploaded")


def create_user_folder(drive, folderName, parentID=None):
    exist_folder_list = drive.ListFile({'q': "'%s' in parents and trashed=false" % parentID}).GetList()

    sub_folder_id = None
    sub_folder_title = None
    for exist_folder in exist_folder_list:
        if exist_folder['title'] == folderName:
            sub_folder_id = exist_folder['id']
            sub_folder_title = exist_folder['title']
            exist_file_list = drive.ListFile({'q': "'%s' in parents and trashed=false" % sub_folder_id}).GetList()
            for exist_file in exist_file_list:
                file1 = drive.CreateFile({'id': exist_file['id']})
                file1.Trash()  # Move file to trash.
                file1.UnTrash()  # Move file out of trash.
                file1.Delete()
            break
    # Create folder
    if not sub_folder_id:
        body = {'title': folderName, 'mimeType': 'application/vnd.google-apps.folder'}
        if parentID:
            body['parents'] = [{'id': parentID}]
        folder = drive.CreateFile(body)
        folder.Upload()
        # Get folder info and print to screen
        sub_folder_title = folder['title']
        sub_folder_id = folder['id']
    print('created user folder. title: %s, id: %s' % (sub_folder_title, sub_folder_id))
    return sub_folder_id


def create_category_folder(drive, folderName, parentID=None):
    exist_folder_list = drive.ListFile({'q': "'%s' in parents and trashed=false" % parentID}).GetList()
    folderid = None
    foldertitle = None
    for exist_folder in exist_folder_list:
        if exist_folder['title'] == folderName:
            folderid = exist_folder['id']
            foldertitle = exist_folder['title']

    # Create folder
    if not folderid:
        body = {'title': folderName, 'mimeType': 'application/vnd.google-apps.folder'}
        if parentID:
            body['parents'] = [{'id': parentID}]
        folder = drive.CreateFile(body)
        folder.Upload()
        # Get folder info and print to screen
        foldertitle = folder['title']
        folderid = folder['id']
    print('created category folder. title: %s, id: %s' % (foldertitle, folderid))
    return folderid


def check_and_create_folder(drive, folder_name, parentID):
    exist_folder_list = drive.ListFile({'q': "'%s' in parents and trashed=false" % parentID}).GetList()
    for exist_folder in exist_folder_list:
        if exist_folder['title'] == folder_name:
            return exist_folder['id']
    body = {'title': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
    if parentID:
        body['parents'] = [{'id': parentID}]
    folder = drive.CreateFile(body)
    folder.Upload()
    folder_id = folder['id']
    print('created one folder. title: %s, id: %s' % (folder_name, folder_id))
    return folder_id


def create_week_folder(drive, year, month, week, parentID):
    week_folder_id = parentID
    for f in (year, month, week):
        try:
            week_folder_id = check_and_create_folder(drive, f, week_folder_id)
        except Exception as e:
            print(e)
            pass
    return week_folder_id

if __name__ == '__main__':

    while True:
        # --- input parameters ---
        df_settings = pd.read_csv('settings.csv')
        insta_username = '' if pd.isna(df_settings.iloc[0, 0]) else df_settings.iloc[0, 0].strip()
        insta_password = '' if pd.isna(df_settings.iloc[0, 1]) else df_settings.iloc[0, 1].strip()
        google_main_folder_id = '' if pd.isna(df_settings.iloc[0, 2]) else df_settings.iloc[0, 2].strip()
        google_sheet_id = '' if pd.isna(df_settings.iloc[0, 3]) else df_settings.iloc[0, 3].strip()
        weekly_work_date_num = 0 if pd.isna(df_settings.iloc[0, 4]) else int(df_settings.iloc[0, 4])
        weekly_work_hour = 0 if pd.isna(df_settings.iloc[0, 5]) else int(df_settings.iloc[0, 5])
        repeat_time = 1 if pd.isna(df_settings.iloc[0, 6]) else df_settings.iloc[0, 6]
        print('-------settings value----------')
        print('weekly_work_date_num: {}'.format(weekly_work_date_num))
        print('weekly_work_hour: {}'.format(weekly_work_hour))
        print('-------------------------------')
        driver_location = "./chromedriver"
        headless = False
        log_location = './logs'
        show_logs = False
        fmt = '%Y-%m-%d %H:%M:%S %Z%z'
        work_day = weekly_work_date_num
        work_hour = weekly_work_hour

        naive_dt = datetime.now()

        present_day = naive_dt.weekday()

        present_hour = naive_dt.hour
        print('-------present value----------')
        print('present_day: {}'.format(present_day))
        print('present_hour: {}'.format(present_hour))
        print('------------------------------')
        # check time to start working module
        if present_day == weekly_work_date_num and present_hour == weekly_work_hour:
            print("matched condition, start working!!!!")
            print('present_time: {}'.format(naive_dt.strftime(fmt)))
            weekOfMonth = week_of_month(naive_dt)
            current_month = naive_dt.strftime("%B")
            current_year = naive_dt.year
            print("week of month : {}".format(weekOfMonth))
            # ----------------
            users = []
            gc = pygsheets.authorize(client_secret='client_secrets.json')
            sh = gc.open_by_key(google_sheet_id)
            # sh = gc.open('Instagram - Web Scrapping')
            wks = sh.sheet1
            df = wks.get_as_df()
            current_week = 'Week ' + str(weekOfMonth)
            week_df = df[df['Week_Month'].isin([current_week])]
            month_df = week_df[week_df['Month'].isin([current_month])]
            work_df = month_df[month_df['Year'].isin([current_year])]

            if work_df.empty:
                continue
            print('--------users working this week-----')
            print(work_df)
            print('user counts: {}'.format(len(work_df)))
            print('-----------------------------------')
            gauth = GoogleAuth()
            gauth.DEFAULT_SETTINGS['client_config_file'] = "client_secrets.json"
            # Try to load saved client credentials
            gauth.LoadCredentialsFile("mycreds.json")
            if gauth.credentials is None:
                # Authenticate if they're not there
                gauth.LocalWebserverAuth()
            elif gauth.access_token_expired:
                # Refresh them if expired
                gauth.Refresh()
            else:
                # Initialize the saved creds
                gauth.Authorize()
            # Save the current credentials to a file
            gauth.SaveCredentialsFile("mycreds.json")

            drive = GoogleDrive(gauth)
            logger = create_logger(log_location, insta_username)
            driver, err_msg = create_driver(driver_location=driver_location, logger=logger, proxy=None, headless=headless)

            if not driver:
                continue

            if not insta_username == '':
                logged_in, message = login_user(driver,
                                                insta_username,
                                                insta_password,
                                                logger,
                                                log_location)
                if not logged_in:
                    highlight_print(insta_username,
                                    message,
                                    "login",
                                    "critical",
                                    logger)
                else:
                    message = "Logged in successfully!"
                    highlight_print(insta_username,
                                    message,
                                    "login",
                                    "info",
                                    logger)
            try:
                for user_number in range(len(work_df)):
                    user_name = work_df.iloc[user_number, 0].split('@')[1]
                    download_path = str(current_year) + '/' +str(current_month)+ '/' + current_week + '/' + work_df.iloc[user_number, 3] + "/" + user_name
                    if not os.path.exists(download_path):
                        os.makedirs(download_path)
                    else:
                        for root, dirs, files in os.walk(download_path):
                            for file in files:
                                os.remove(os.path.join(root, file))
                    week_folder_id = create_week_folder(drive, str(current_year), str(current_month), str(current_week), google_main_folder_id)
                    category_folder_id = create_category_folder(drive, work_df.iloc[user_number, 3], week_folder_id)
                    user_folder_id = create_user_folder(drive, user_name, category_folder_id)
                    download_photos(driver, user_name, download_path, logger, 12)
                    upload_2_google(drive, download_path, user_folder_id)
            except Exception as e:
                print(e)
                pass
            driver.close()

        time.sleep(60*repeat_time)
