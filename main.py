from flask import Flask, render_template, request, jsonify
import requests
import os
import random
import string
import websocket
import uuid
import json
import urllib.request
import urllib.parse
from PIL import Image
import time
import base64


#server URL
server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())
queue_url = "http://127.0.0.1:8188/queue"

#workflows
configurations = {
    "1": {
        "file_path": "workflows/change_outfit.json",
        "target_node_id": "978",
        "seed": "949"
    },
    "2": {
        "file_path": "workflows/make_nsfw.json",
        "target_node_id": "903",
        "seed": "64"
    },
    "3": {
        "file_path": "workflows/creative.json",
        "target_node_id": "1000",
        "seed": "878"
    }
}



def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())

def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break #Execution is done
        else:
            continue #previews are binary data

    history = get_history(prompt_id)[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
            output_images[node_id] = images_output

    return output_images

def generate_random_numbers(length=13):
    #Cgetting random seed
    snumbers = string.digits
    return ''.join(random.choice(snumbers) for _ in range(length))

def run_engine(file_path, target_node_id, chosen_image, user_prompt, seed):


    #Timer Start
    start_time = time.time()


    # #Load Image
    image_path = os.path.join(os.getcwd(), os.path.join("uploads", chosen_image))




    #Loading prompt
    with open(file_path, "r") as json_file:
        json_data = json_file.read()
    prompt = json.loads(json_data)


    
    xseed = str(seed)  

    #Changing the original Prompt
    prompt["133"]["inputs"]["image"] = image_path
    prompt["999"]["inputs"]["Text"] = user_prompt
    prompt[xseed]["inputs"]["seed"] = generate_random_numbers()


    #websocket and start process
    ws = websocket.WebSocket()
    ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))

    #getting processed image by node_id (outfit:978, nsfw:903, creative:1000)
    images = get_images(ws, prompt)



        
        
    #getting images
    encoded_images = []
    for node_id in images:
        if node_id == target_node_id:
            for image_data in images[node_id]:
                encoded_image = base64.b64encode(image_data).decode('utf-8')
                encoded_images.append(encoded_image)
                generate_image(image=image_data)



    #Timer end
    end_time = time.time()
    elapsed_time = end_time - start_time
    

    return encoded_images, elapsed_time





def generate_image(image):
    
    def generate_random_numbers(length=13):
        #Cgetting random seed
        snumbers = string.digits
        return ''.join(random.choice(snumbers) for _ in range(length))
    
    ximage_path = os.path.join(os.getcwd(), os.path.join("generations", generate_random_numbers() + ".png"))
    with open(ximage_path, 'wb') as fh:
        fh.write(image)
        


def generate_random_filename(length=10):
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(length))

def get_queue_size_from_url(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            response_json = response.json()
            queue_running = response_json.get('queue_running', [])
            prompt_count = len(queue_running)
            print("Number of prompts in queue:", prompt_count)
            return prompt_count
        else:
            print("Failed to fetch queue information. Status code:", response.status_code)
            return None
    except Exception as e:
        print("An error occurred:", e)
        return None

app = Flask(__name__, template_folder='.')

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run_option', methods=['GET', 'POST'])
def run_option():
    
    queue = None  # Initialize queue size variable
    
    if request.method == 'POST':
        
        xurl = request.form.get('url')
        xfile = request.files['file']

        if xurl:
            response = requests.get(xurl, verify=False)
            if response.status_code == 200:
                extension = xurl.split(".")[-1]
                yfilename = generate_random_filename() + "." + extension
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], yfilename)
                with open(filepath, "wb") as file:
                    file.write(response.content)
        else:
            yfilename = generate_random_filename() + "_" + xfile.filename
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], yfilename)
            xfile.save(filepath)    
        
    if request.method == 'GET' or request.method == 'POST':
        if 'check_queue' in request.args:  # Check if the "check_queue" parameter is present
            url_to_check = queue_url  # Replace with the actual URL for the queue information
            queue = get_queue_size_from_url(url_to_check)    
        
        

    user_prompt = request.form['user_prompt']
    selected_option = request.form['option']

    if selected_option in configurations:
        config = configurations[selected_option]
        file_path = config["file_path"]
        target_node_id = config["target_node_id"]
        seed = config["seed"]

        chosen_image = yfilename
        encoded_images, elapsed_time = run_engine(file_path, target_node_id, chosen_image, user_prompt, seed)


        
        return render_template('index.html', encoded_images=encoded_images, elapsed_time=elapsed_time, queue=queue )
    else:
        return "Invalid option."
    
@app.route('/check_queue', methods=['GET'])
def check_queue():
    url_to_check = queue_url  # Replace with the actual URL for the queue information
    queue = get_queue_size_from_url(url_to_check)
    return jsonify({"queue": queue})

if __name__ == '__main__':
    app.run(debug=False)