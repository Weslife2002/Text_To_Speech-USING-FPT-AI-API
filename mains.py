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
        # The url is not ready then wait for 5 second

    return r.content

async def async_text_list_to_speech(content_list):
    list = await asyncio.gather(*(text_to_speech(content_list[_]) for _ in range(4)))
    return list

if __name__ == "__main__":
    import time
    s = time.perf_counter()
    content_list = ["Chàoo", "Mìnhh", "Mình thíchh", "Tạm biệtt"]
    a = asyncio.run(async_text_list_to_speech(content_list))
    print(a)
    elapsed = time.perf_counter() - s
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")