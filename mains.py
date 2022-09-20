import asyncio
import copy
import json
import os
import re
import time
from typing import TypeVar, Union

import aiohttp
from pydub import AudioSegment

DATA_FILE = './data/data.json'

API_KEY = '0OcaRZcz0ZYNZzbOS6p0oaSAWNed362s'
SERVICE_URL = 'https://api.fpt.ai/hmi/tts/v5'
HEADERS = {
    'api-key': API_KEY,
    'speed': '',
    'voice': 'minhquang',
    'format': 'wav'
}

T = TypeVar('T')


class RawData:
    _content = {}
    _lock = asyncio.Lock()

    @classmethod
    async def get_by_key(cls, key, default: T) -> T:
        async with cls._lock:
            if not cls._content:
                try:
                    cls._content = json.load(open(DATA_FILE, 'r', encoding='utf-8'))
                except FileNotFoundError:
                    cls._content = {}
                cls._content['unique_id'] = cls._content.get('unique_id', '0')
                cls.save()
            return cls._content.get(key, default)

    @classmethod
    async def set_by_key(cls, key, value):
        async with cls._lock:
            cls._content[key] = copy.deepcopy(value)
            cls.save()

    @classmethod
    async def get_unique_id(cls):
        async with cls._lock:
            cls._content['unique_id'] = str(int(cls._content['unique_id']) + 1)
            cls.save()
            return cls._content['unique_id']

    @classmethod
    def save(cls):
        json.dump(cls._content, open(DATA_FILE, 'w+', encoding='utf-8'), indent=4, ensure_ascii=False)


class Data:
    @classmethod
    async def get_audio_name(cls, text: str) -> str:
        """
        Get audio name from text.

        :param text: Text to search
        :return: Audio name
        """
        text = text.strip().lower()

        data = await RawData.get_by_key('audio_files', {})
        for audio_id, audio_text in data.items():
            if audio_text == text:
                return f'audio_{audio_id}.wav'
        else:
            new_id = await RawData.get_unique_id()
            await RawData.set_by_key('audio_files', {**data, new_id: text})
            return f'audio_{new_id}.wav'

    @classmethod
    async def get_base_script_name(cls, base_script: str) -> str:
        """
        Get base script name from text.

        :param base_script: Text to search
        :return: Base script name
        """
        base_script = base_script.strip().lower()

        data = await RawData.get_by_key('base_script_files', {})
        for base_script_id, base_script_text in data.items():
            if base_script_text == base_script:
                return f'base_script_{base_script_id}.wav'
        else:
            new_id = await RawData.get_unique_id()
            await RawData.set_by_key('base_script_files', {**data, new_id: base_script})
            return f'base_script_{new_id}.wav'

    @classmethod
    async def get_base_script_id(cls, base_script: str) -> str:
        """
        Get base script id from text.

        :param base_script: Text to search
        :return: Base script id
        """
        base_script = base_script.strip().lower()

        data = await RawData.get_by_key('base_script_files', {})
        for base_script_id, base_script_text in data.items():
            if base_script_text == base_script:
                return base_script_id
        else:
            new_id = await RawData.get_unique_id()
            await RawData.set_by_key('base_script_files', {**data, new_id: base_script})
            return new_id

    @classmethod
    async def set_base_script_positions(cls, base_script: str, positions: list):
        """
        Set base script fill in positions.

        :param base_script: Base script name
        :param positions: Positions
        """
        base_script = base_script.strip().lower()

        base_script_id = await cls.get_base_script_id(base_script)
        await RawData.set_by_key('base_script_positions', {
            **await RawData.get_by_key('base_script_positions', {}),
            base_script_id: positions
        })

    @classmethod
    async def get_base_script_positions(cls, base_script: str) -> list[dict[str, Union[int, str]]]:
        """
        Get base script fill in positions.

        :param base_script: Base script name
        :return: Positions
        """
        base_script = base_script.strip().lower()

        base_script_id = await cls.get_base_script_id(base_script)
        return (await RawData.get_by_key('base_script_positions', {}))[base_script_id]


async def read_raw_audio_file(name: str) -> bytes:
    """
    Read audio file and return the audio content.

    :param name: Name of the audio file
    :return: Audio content
    """
    return open(name, 'rb').read()


async def read_audio_file(name: str) -> AudioSegment:
    """
    Read audio file and return the audio content.

    :param name: Name of the audio file
    :return: Audio content
    """
    return await asyncio.to_thread(AudioSegment.from_wav(name))


async def text_to_speech(payload: str) -> AudioSegment:
    """
    Convert text to speech.

    :param payload: Text to convert
    :return: Audio content
    """
    audio_file = await Data.get_audio_name(payload)
    file_path = f"./data/{audio_file}"
    if os.path.exists(file_path):
        return await read_raw_audio_file(file_path)

    audio = await _text_to_speech(payload)
    await asyncio.to_thread(audio.export, file_path, format='wav')
    return audio


async def _text_to_speech(payload: str) -> AudioSegment:
    """
    Request text to speech from FPT.AI.

    :param payload: Text to convert
    :return: Audio content
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(SERVICE_URL, data=payload.encode('utf-8'), headers=HEADERS) as resp:
            url = (await resp.json())['async']

        while True:
            async with session.get(url, headers=HEADERS) as resp:
                print(f"... Fetching content: [ {payload} ] from url: {url} ...")
                if resp.status != 404:
                    print(f"... Content fetched: [ {payload} ] from url: {url} ...")
                    return AudioSegment(await resp.read())
                else:
                    await asyncio.sleep(5)


async def get_base_script_audio(base_script: str) -> AudioSegment:
    """
    Get the base script and return the audio content with the index of the base script or try to generate the base
    script if it doesn't exist.

    :return: Audio content and index of the base script
    """
    base_script_name = await Data.get_base_script_name(base_script)
    file_path = f"./data/{base_script_name}"
    if os.path.exists(file_path):
        return await read_raw_audio_file(file_path)

    content = await _generate_base_script_audio(base_script)
    await asyncio.to_thread(content.export, file_path, format='wav')
    return content


async def _generate_base_script_audio(base_script: str) -> AudioSegment:
    """
    Generate base script audio.

    :param base_script: Base script
    :return: Audio content
    """
    base_script_list = re.split(r'\$[^\s$]+\$', base_script)
    variable_list = re.findall(r'\$([^\s$]+)\$', base_script) + ['']

    # Create time_list data
    time_list_data = await asyncio.gather(
        *[text_to_speech(content) for content in base_script_list]
    )
    position_list = []
    content = AudioSegment.empty()

    for index, audio_data in enumerate(time_list_data):
        content += audio_data

        position_list.append({
            "position": len(content),
            "variable": variable_list[index]
        })

    await Data.set_base_script_positions(base_script, position_list)
    return content


async def prepare_content(base_script: str, fill_in_list: list[dict[str, str]]):
    """
    Prepare the content for the base script.

    :param base_script: Base script
    :param fill_in_list: Fill in list
    """
    # Prepare base script
    await get_base_script_audio(base_script)

    # Prepare fill in script
    position_list = await Data.get_base_script_positions(base_script)
    await asyncio.gather(*[
        _get_fill_in_sounds(fill_in_data, position_list) for fill_in_data in fill_in_list
    ])


async def _get_fill_in_sounds(fill_in_data: dict[str, str], position_list: list[dict[str, str]]):
    """
    Get fill in sounds.

    :param fill_in_data: Fill in data
    :param position_list: Position list
    :return: Audio content
    """
    fill_in_value_list = [
        fill_in_data[position_list[index]["variable"]] for index in range(len(fill_in_data))
    ]
    fill_in_sounds = await asyncio.gather(*[text_to_speech(content) for content in fill_in_value_list])
    return fill_in_sounds


async def get_final_audio(base_script: str, fill_in_data: dict[str, str]) -> AudioSegment:
    """
    Fill data to base script.

    :param base_script: Base script
    :param fill_in_data: Fill in data
    """
    base_script_audio = await get_base_script_audio(base_script)
    position_list = await Data.get_base_script_positions(base_script)

    final_script = base_script_audio[:position_list[0]["position"]]

    # Convert all the variable to audio
    fill_in_sounds = await _get_fill_in_sounds(fill_in_data, position_list)

    for i in range(len(fill_in_data)):
        if position_list[i]["variable"]:
            current_position = position_list[i]["position"]
            next_position = position_list[i + 1]["position"]

            final_script += fill_in_sounds[i]
            final_script += base_script_audio[current_position:next_position]

    return final_script


async def _main():
    os.makedirs('data', exist_ok=True)

    s = time.perf_counter()
    base = '''Xin chào tôi $friend$Mình đéo là $name$Mình cực kỳ thích $hobby$Tạm gặp lại biệt'''
    all_fill_in_data = [
        {
            "friend": "Quang Khánh Lương",
            "name": "Duy Tân Trương",
            "hobby": "gái đẹp đẹp"
        },
        {
            "friend": "Quang Duy ABC",
            "name": "Duy Tân Á",
            "hobby": "gái đẹp âu"
        },
        {
            "friend": "Quang Dũng Ạ",
            "name": "Duy Tân Ả",
            "hobby": "gái đẹp Ã"
        }
    ]

    await prepare_content(base, all_fill_in_data)

    elapsed = time.perf_counter() - s
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")


async def _test():
    base = '''Xin chào tôi $friend$Mình đéo là $name$Mình cực kỳ thích $hobby$Tạm gặp lại biệt'''
    all_fill_in_data = [
        {
            "friend": "Quang Khánh Lương",
            "name": "Duy Tân Trương",
            "hobby": "gái đẹp đẹp"
        },
        {
            "friend": "Quang Duy ABC",
            "name": "Duy Tân Á",
            "hobby": "gái đẹp âu"
        },
        {
            "friend": "Quang Dũng Ạ",
            "name": "Duy Tân Ả",
            "hobby": "gái đẹp Ã"
        }
    ]
    return await get_final_audio(base, all_fill_in_data[0])


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(_main())
    # audio = asyncio.get_event_loop().run_until_complete(_test())
    # audio.export('final.wav', format='wav')
