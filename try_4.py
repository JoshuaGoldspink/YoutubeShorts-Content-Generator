from moviepy.config import change_settings
from moviepy.editor import *
from moviepy.editor import concatenate_audioclips
from praw import Reddit
from selenium.webdriver.chrome.options import Options
import pyttsx3
from selenium.common.exceptions import TimeoutException
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
from selenium.webdriver.chrome.service import Service as ChromeDriverService
from moviepy.editor import concatenate_videoclips
import os
import shutil

imagemagick_path = r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"
change_settings({"IMAGEMAGICK_BINARY": imagemagick_path})

CLIENT_ID = ''
SECRET_KEY = ''


def clear_directory_contents(dir_path):
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    os.makedirs(dir_path)

# Fetch Reddit content
with open('identifier.txt','r') as f:
    pw = f.read()

def fetch_reddit_content(subreddit_name, num_comments, post_position=1):
    reddit = Reddit(
        client_id=CLIENT_ID,
        client_secret=SECRET_KEY,
        password=pw,
        user_agent="content by u\Mevmo",
        username="Mevmo",
    )
    subreddit = reddit.subreddit(subreddit_name)
    post = None

    for idx, p in enumerate(subreddit.top(limit=post_position)):
        if idx == post_position - 1:
            post = p
            break


    comments = [comment for comment in list(post.comments)[:num_comments] if len(comment.body) <= 250]

    # Return the post URL and comment IDs in addition to the title and comments
    comment_ids = [comment.id for comment in comments]

    return post.title, post.url, comment_ids, comments




def create_audio_files(title, comments):
    engine = pyttsx3.init()
    audio_dir = "audio_files"

    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)

    # Get the current speaking rate
    current_rate = engine.getProperty('rate')
    # Set the new speaking rate to 1.2x the current rate
    engine.setProperty('rate', current_rate * 1.2)

    engine.save_to_file(title, os.path.join(audio_dir, "title.mp3"))
    engine.runAndWait()

    for idx, comment in enumerate(comments):
        engine.save_to_file(comment.body, os.path.join(audio_dir, f"comment_{idx + 1}.mp3"))
        engine.runAndWait()


def create_video(background_video_filename, title, comments, output_name, successful_comment_indices):
    #background_video = VideoFileClip(background_video_filename)
    # Read the background video from the 'background_videos' folder
    background_video = VideoFileClip(os.path.join("background_videos", background_video_filename))

    audio_files_dir = "audio_files"
    screenshots_dir = "screenshots"

    # Load the audio files and images only for successful comment indices
    title_audio = AudioFileClip(os.path.join(audio_files_dir, "title.mp3"))
    title_image = ImageClip(os.path.join(screenshots_dir, "screenshot_cropped_0.png"), duration=title_audio.duration).resize(0.5)

    comment_audios = [AudioFileClip(os.path.join(audio_files_dir, f"comment_{idx + 1}.mp3")) for idx in
                      successful_comment_indices]

    comment_images = [
        ImageClip(os.path.join(screenshots_dir, f"screenshot_cropped_{idx + 1}.png"), duration=audio.duration)
            .resize(0.5)  # Resize the image to half its original size
        for idx, audio in zip(successful_comment_indices, comment_audios)]

    # Concatenate the audio clips
    concatenated_audio = concatenate_audioclips([title_audio] + comment_audios)

    # Concatenate the ImageClips
    concatenated_images = concatenate_videoclips([title_image] + comment_images, method="compose")

    # Overlay the concatenated images on the background video
    final_video = CompositeVideoClip([background_video, concatenated_images.set_position("center")])

    # Set the concatenated audio on the video
    final_video = final_video.set_audio(concatenated_audio)

    # Calculate the total duration of the concatenated audio, and cap it at 60 seconds
    total_audio_duration = min(concatenated_audio.duration, 30)

    # Trim the video to match the total_audio_duration
    final_video = final_video.subclip(0, total_audio_duration)

    # Resize and crop the video to a 9:16 aspect ratio
    width, height = final_video.size
    new_width = int(height * (9 / 16))  # Calculate new width
    x_start = (width - new_width) // 2  # Calculate x_start position
    final_video = final_video.crop(x1=x_start, x2=x_start + new_width)  # Crop the video

    # Export the final video to the 'output_files' folder
    bitrate = '5000k'
    threads = '2'
    output_folder = "output_files"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    outputFile = os.path.join(output_folder, f"{output_name}.mp4")
    final_video.write_videofile(
        outputFile,
        codec='mpeg4',
        threads=threads,
        bitrate=bitrate,
    )



def capture_comment_screenshot(comment_text, number,url,screenshots_dir,driver):

    # Replace comment_text with the largest substring that doesn't contain an apostrophe or an asterisk
    if "'" in comment_text:
        comment_text = max(comment_text.split("'"), key=len)
    if "*" in comment_text:
        comment_text = comment_text.replace('*', '')

    try:
        comment = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{comment_text}')]"))
        )
    except TimeoutException:
        print("Comment not found")
        return False

    # Scroll to the comment
    driver.execute_script("arguments[0].scrollIntoView();", comment)

    # Adjust the scroll to center the comment
    driver.execute_script("window.scrollBy(0, -window.innerHeight/2 + arguments[0].clientHeight/2);", comment)

    # Get the comment bounding rectangle
    # Take a screenshot
    driver.save_screenshot('screenshot_full.png')

    # Crop the screenshot
    image = Image.open('screenshot_full.png')
    if number == 0:
        #cropped_image = image.crop((30, 330, 850, 600))
        cropped_image = image.crop((200, 390, 1200, 800))

    else:
        #cropped_image = image.crop((30, 330, 830, 500)) #old
        cropped_image = image.crop((250, 330, 950, 550)) #new
    cropped_image.save(os.path.join(screenshots_dir, f'screenshot_cropped_{number}.png'))
    return True



def take_screenshots(post_url, comment_ids,title):
    # Set up the web driver with the appropriate options
    print("Taking Title Screenshot")
    options = Options()
    options.headless = True
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)

    # Create the screenshots directory if it doesn't exist
    screenshots_dir = "screenshots"
    if not os.path.exists(screenshots_dir):
        os.makedirs(screenshots_dir)

    # Take a screenshot of the title
    driver.get(post_url)
    time.sleep(2)  # Allow the page to load

    # Set the path to your webdriver (e.g., ChromeDriver)
    webdriver_path = 'C:\\Users\\joshu\\Downloads\\chromedriver_win32\\chromedriver.exe'

    # Create a ChromeDriverService and a new browser instance
    service = ChromeDriverService(executable_path=webdriver_path)
    driver = webdriver.Chrome(service=service)

    # Open the URL
    print(post_url)
    driver.get(post_url)


    # Wait for the page to load
    time.sleep(10)


    #Take Title Screenshot
    capture_comment_screenshot(title[:30], 0, post_url, screenshots_dir, driver)
    time.sleep(1)

    # Take screenshots of the comments
    print("Taking Comment Screenshots")
    successful_comment_indices = []
    for idx, comment in enumerate(comments):
        print("Finding Comment:   ", comment.body[:30])
        if capture_comment_screenshot(comment.body[:30], idx + 1, post_url, screenshots_dir, driver):
            successful_comment_indices.append(idx)
        time.sleep(1)

    # Close the browser
    driver.quit()
    return successful_comment_indices


def clear_directory_contents2(dir_path):
    for filename in os.listdir(dir_path):
        file_path = os.path.join(dir_path, filename)

        # Try multiple times to remove the file
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                break  # Successfully removed the file, break the loop
            except PermissionError:
                if attempt < max_attempts - 1:  # Don't sleep on the last attempt
                    time.sleep(0.5)  # Sleep for 500 milliseconds
                else:
                    raise  #


for i in range(8,20):
    # Clear the Folders
    time.sleep(4)
    screenshots_dir = 'C:\\Users\\joshu\\PycharmProjects\\content_generator\\screenshots'
    audio_dir = 'C:\\Users\\joshu\\PycharmProjects\\content_generator\\audio_files'
   #clear_directory_contents2(screenshots_dir)
    #clear_directory_contents2(audio_dir)

    # Fetch the Reddit content and call the function to take screenshots
    print("Getting Data")
    # title, post_url, comment_ids, comments = fetch_reddit_content("AskReddit", 4)
    title, post_url, comment_ids, comments = fetch_reddit_content("unpopularopinion", 10, post_position=i)
    print(title)

    # Call the function to create audio files after fetching the Reddit content
    print("Generating Audio")
    create_audio_files(title, comments)

    # Take Screenshots
    print('Taking Screenshots')
    # take_screenshots(post_url, comment_ids,title)
    successful_comment_indices = take_screenshots(post_url, comments, title)

    # Create Video
    print("Creating Video")

    background_video_filename = f"new_parkour_{i}.mp4"
    output_name = f'unpopular_opinion{i}'
    create_video(background_video_filename, title, comments, output_name, successful_comment_indices)
    time.sleep(2)

