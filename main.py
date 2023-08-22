from flask import Flask, render_template, request, jsonify
import requests
import os
import random
import string
import websocket
import uuid
import json
from PIL import Image
import base64
from io import BytesIO
import io


server_address = "Create and enter a valid server!"
client_id = str(uuid.uuid4())
queue_url = "http://" + server_address + "/queue"
#workflows
configurations = {
    "1": {
        "file_path": "workflows/CosplayOLD.json",
        "target_node_id": "978",
        "ksampler": "949",
        "promptnode": "999",
        "imagenode": "133"
    },
    "2": {
        "file_path": "workflows/adult.json",
        "target_node_id": "903",
        "ksampler": "64",
        "promptnode": "999",
        "imagenode": "133"
    },
    "3": {
        "file_path": "workflows/creative.json",
        "target_node_id": "1000",
        "ksampler": "878",
        "promptnode": "999",
        "imagenode": "133"
    },
    "4": {
        "file_path": "workflows/CosplayCloth.json",
        "target_node_id": "1106",
        "ksampler": "1031",
        "promptnode": "1058",
        "imagenode": "133"
    },
    "5": {
        "file_path": "workflows/CosplayWhole.json",
        "target_node_id": "1106",
        "ksampler": "1031",
        "promptnode": "1058",
        "imagenode": "133"
    },
    "6": {
        "file_path": "workflows/HairStyle.json",
        "target_node_id": "104",
        "ksampler": "24",
        "promptnode": "76",
        "imagenode": "1"
    },
    "7": {
        "file_path": "workflows/changeback.json",
        "target_node_id": "79",
        "ksampler": "10",
        "promptnode": "39",
        "imagenode": "12"
    }
}

def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    url = "http://{}/prompt".format(server_address)
    response = requests.post(url, data=data, headers={'Content-Type': 'application/json'})
    return response.json()

def get_image_name(prompt):
    progress = 0
    ws = websocket.WebSocket() 
    ws.connect("wss://{}/ws?clientId={}".format(server_address, client_id))
    prompt_id = queue_prompt(prompt)['prompt_id']
    try:
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'progress':
                    value = message['data']['value']
                    max = message['data']['max']
                    progress = int(100 * value / max)
                if message['type'] == 'executed':
                    if 'images' in message['data']['output']:
                        images = message['data']['output']['images']
                        for image in images:
                            if 'type' in image and image['type'] == 'output':
                                if 'filename' in image:
                                    filename = image['filename']
                                    print(filename)
                                    url = "http://{}/view?filename={}".format(server_address, filename)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break #Execution is done
            else:
                continue #previews are binary data

    finally:
        ws.close()
        print("okai im done")
    return url

def image_in_base64(url):
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue())
    img_str = img_str.decode('utf-8')
    img_bytes = base64.b64decode(img_str)
    generate_image(img_bytes)
    return img_str

def generate_random_numbers(length=13):
    #Cgetting random seed
    snumbers = string.digits
    return ''.join(random.choice(snumbers) for _ in range(length))

def engine(prompt_node, image_node, file_path, chosen_image, user_prompt, ksampler):

    # #Load Image
    image_path = os.path.join(os.getcwd(), os.path.join("uploads", chosen_image))

    #Loading prompt
    with open(file_path, "r") as json_file:
        json_data = json_file.read()
    prompt = json.loads(json_data)
    xprompt_node = str(prompt_node)
    ximage_node = str(image_node)
    xksampler = str(ksampler)  

    # Construct files dict for upload  
    files = {'image': open(image_path, 'rb')}
    url = "http://{}".format(server_address)
    requests.post(url + "/upload/image", files=files)
    

    #Changing Prompt
    prompt[ximage_node]["inputs"]["image"] = chosen_image
    prompt[xprompt_node]["inputs"]["text"] = user_prompt
    prompt[xksampler]["inputs"]["seed"] = generate_random_numbers()
    
    
    encoded_images = []
    encoded_image = image_in_base64(get_image_name(prompt))
    encoded_images.append(encoded_image)

    return encoded_images

def generate_image(image):
    
    def generate_random_numbers(length=6):
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
    
app = Flask(__name__, template_folder='templates')

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('indexmain.html', server_address=server_address)

@app.route('/generate', methods=['GET', 'POST'])
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
        ksampler = config["ksampler"]
        prompt_node = config["promptnode"]
        image_node = config["imagenode"]

        chosen_image = yfilename
        encoded_images = engine(prompt_node, image_node, file_path, chosen_image, user_prompt, ksampler)


        
        return render_template('index.html', encoded_images=encoded_images, queue=queue, server_address=server_address)
    else:
        return "Invalid option."


@app.route('/check_queue', methods=['GET'])
def check_queue():
    url_to_check = queue_url  # Replace with the actual URL for the queue information
    queue = get_queue_size_from_url(url_to_check)
    return jsonify({"queue": queue})

@app.route('/update_server')
def update_server():
    new_address = request.args.get('address').strip().rstrip('/')
    new_address = new_address.replace('http://', '')
    new_address = new_address.replace('https://', '')
    global server_address
    server_address = new_address
    return "OK"

@app.route('/check_server')
def check_server():
  try:
    response = requests.get("http://" + server_address)
    if response.status_code == 200:
      return "Server is up!"
    else:
      return "Server returned status code %s" % response.status_code
  except:
    return "Server is down!"

@app.route('/load_default')
def load_default():
  global server_address
  server_address = "127.0.0.1:8188"
  return "OK"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)