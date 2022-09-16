import requests
import json
from pydub import AudioSegment
import time
import tempfile
import os
import re
import asyncio


api_key = '0OcaRZcz0ZYNZzbOS6p0oaSAWNed362s'

async def text_to_speech(payload):
    # print(payload)
    service_url = 'https://api.fpt.ai/hmi/tts/v5'
    
    headers = {
        'api-key': api_key,
        'speed': '',
        'voice': 'minhquang',
        'format': 'wav'
    }
    response = requests.request('POST', service_url, data=payload.encode('utf-8'), headers=headers)

    url = response.json()["async"]

    r = requests.get(url)
    while r.status_code == 404:
        print(f"... Fetching content: [ {payload} ] from url: {url} ...")
        await asyncio.sleep(30)
        r = requests.get(url)
        # The url is not ready then wait for 30 seconds

    return r.content

async def fill_in_text_to_speech(payload):
    fill_in_script_dict = json.loads(open("./data/fill_in_dict.txt", "r").read())

    index = -1
    for fill_in_script_item in fill_in_script_dict:
        if(fill_in_script_item["content"]) == payload:
            index = fill_in_script_item["index"]
    if index == -1:
        a = await text_to_speech(payload)
        fill_in_script_dict.append({"content":payload, "index":len(fill_in_script_dict)})
        open(f"./data/fill_in_dict.txt", "w").write(json.dumps(fill_in_script_dict))
        # Save the content to the wav file
        open(f"./data/fill_in_script_{len(fill_in_script_dict)-1}.wav", "wb").write(a)
        return a
    else:
        return open(f"./data/fill_in_script_{index}.wav", "rb").read()

# Get the index of the content -> If available: return the file content
                            #  -> If unavailable: await the response and go on
    


async def async_text_list_to_speech(content_list):
    list = await asyncio.gather(*(text_to_speech(content_list[_]) for _ in range(len(content_list))))
    return list

async def async_fill_in_text_list_to_speech(content_list):
    list = await asyncio.gather(*(fill_in_text_to_speech(content_list[_]) for _ in range(len(content_list))))
    return list

def generate_base_script():
    # Variables init
    base_script = open("base_script.txt", "r").read()
    base_script_dict = json.loads(open("./data/base_script_dict.txt", "r").read())
    base_script_list = re.split(r'\$[^$]+\$', base_script)
    variable_list = re.findall(r'\$[^$]+\$', base_script)
    variable_list.append("")
    base_script_sound = None
    index = 0

    ## Debug
    print(base_script_list)
    print(variable_list)
    print(base_script_dict)


    # Check wav file available for the script
    for content in base_script_dict:
        if content["content"] == base_script:
            index = content['index']
            base_script_sound = AudioSegment.from_wav(f"./data/base_script_{index}.wav")
    
    # If the base_script isn't available then move on
    if base_script_sound == None:
        index = len(base_script_dict)

        # Update ./data/base_script_dict.txt file
        base_script_dict.append({"content": base_script, "index": index})
        open(f"./data/base_script_dict.txt", "w+").write(json.dumps(base_script_dict))

        # Create time_list data
        time_list_data = asyncio.run(async_text_list_to_speech(base_script_list))

        # Create position_list data
        position_list = []
        for _ in range(len(base_script_list)):
            position_list.append({"position" : base_text_to_speech(time_list_data[_], index), "variable" : variable_list[_][1:-1]})

        # Transfer the position_list data to file position_list_[index].txt
        open(f"./data/position_list_{index}.txt", "w+").write(json.dumps(position_list))
        base_script_sound == AudioSegment.from_wav(f"./data/base_script_{index}.wav")
    
    return [base_script_sound, index]

def base_text_to_speech(content, index):
    try:
        sound1 = AudioSegment.from_wav(f"./data/base_script_{index}.wav")
        open("./data/new_base_script.wav", 'wb').write(content)
        sound2 = AudioSegment.from_wav("./data/new_base_script.wav")

        combined_sounds = sound1 + sound2
        combined_sounds.export(f"./data/base_script_{index}.wav", format="wav")
    except:
        open(f"./data/base_script_{index}.wav", 'wb').write(content)
        combined_sounds = AudioSegment.from_wav(f"./data/base_script_{index}.wav")
    return len(combined_sounds)

def add_content_to_base_script(base_script_sound, index):
    count = 0
    fill_in_script_list = json.loads(open("fill_in_script_list.txt", "r").read())
    position_list = json.loads(open(f"./data/position_list_{index}.txt", "r").read())

    print(fill_in_script_list)
    print(position_list)  

    for fill_in_script in fill_in_script_list:
        final_script = base_script_sound[:position_list[0]["position"]]
        temp_file_list = []

        # Convert all fill_in_variable_value to sound.
        fill_in_value_list = [fill_in_script[position_list[_]["variable"]] for _ in range(len(fill_in_script))]

        fill_in_sound = asyncio.run(async_fill_in_text_list_to_speech(fill_in_value_list))

        for _ in range(len(fill_in_script)):
            if position_list[_]["variable"] != "":
                temp_file_list.append(tempfile.TemporaryFile())
                temp_file_list[_].write(fill_in_sound[_])

        for _ in range(len(fill_in_script)):
            final_script += AudioSegment.from_wav(temp_file_list[_])
            final_script += base_script_sound[position_list[_]["position"] : position_list[_+1]["position"]]

        final_script.export(f"final_script_{index}_{count}.wav", format = "wav")
        count += 1

if __name__ == "__main__":
    # Check file base_script_dict.txt and file fill_in_dict.txt available or not
    if os.path.exists("./data/base_script_dict.txt") == False:
        open("./data/base_script_dict.txt", 'w').write("[]")
    if os.path.exists("./data/fill_in_dict.txt") == False:
        open("./data/fill_in_dict.txt", 'w').write("[]")

    s = time.perf_counter()
    base_script_sound, index = generate_base_script()
    add_content_to_base_script(base_script_sound, index)
    elapsed = time.perf_counter() - s
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")
