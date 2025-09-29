# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Storycraft prompts
def get_scenario_prompt(
    pitch: str, num_scenes: int, style: str, language_name: str, language_code: str
) -> str:
    return f"""
    You are tasked with generating a creative scenario for a short movie and creating prompts for storyboard illustrations. Follow these instructions carefully:
1. First, you will be given a story pitch. This story pitch will be the foundation for your scenario.

<pitch>
{pitch}
</pitch>

2. Generate a scenario in {language_name} for a movie based on the story pitch. Stick as close as possible to the pitch. The style of the movie is {style}. Do not include children in your scenario.

3. What Music Genre will best fit this video, pick from:
- Alternative & Punk
- Ambient
- Children's
- Cinematic
- Classical
- Country & Folk
- Dance & Electronic
- Hip-Hop & Rap
- Holiday
- Jazz & Blues
- Pop
- R&B & Soul
- Reggae
- Rock

4. What is the mood of this video, pick from:
- Angry
- Bright
- Calm
- Dark
- Dramatic
- Funky
- Happy
- Inspirational
- Romantic
- Sad

5. Generate a short description of the music, in English only, that will be used in the video. No references to the story, no references to known artists or songs.

6. Format your output as follows:
- First, provide a detailed description of your scenario in {language_name}.
- Then from this scenario provide a short description of each character in the story inside the characters key.
- Then from this scenario provide a short description of each setting in the story inside the settings key.
- Then, optionally, and only for very important props (products for ads, recurring objects, vehicles), if any, 0 to 2 props max, a short description of each prop important for the story

Format the response as a JSON object.
Here's an example of how your output should be structured:
{{
 "scenario": "[Brief description of your creative scenario based on the given story pitch]",
 "genre": "[Music genre]",
 "mood": "[Mood]",
 "music": "[Short description of the music that will be used in the video, no references to the story, no references to known artists or songs]",
 "language": {{
   "name": "{language_name}",
   "code": "{language_code}"
 }},
 "characters": [
  {{
    "name": "[character 1 name]",
    "voice": "[character's voice description. One sentence.]",
    "description": [
      "character 1 description in {language_name}",
      "Be hyper-specific and affirmative and short, one sentence max. Include age, gender, ethnicity, specific facial features if any, hair style and color, facial hair or absence of it for male, skin details and exact clothing, including textures and accessories."
      ]
  }}
 ],
 "settings": [
  {{
    "name": "[setting 1 name]",
    "description": [
      "setting 1 description in {language_name}",
      "This description establishes the atmosphere, lighting, and key features that must remain consistent.",
      "Be Evocative and short, one sentence max: Describe the mood, the materials, the lighting, and even the smell or feeling of the air."
    ]
  }}
 ],
 "props": [
  {{
    "name": "[prop 1 name]",
    "description": [
      "prop 1 description in {language_name}",
      "This description establishes the atmosphere, lighting, and key features that must remain consistent.",
      "Be Evocative and short, one sentence max: Describe the mood, the materials, the lighting, and even the smell or feeling of the air."
    ]
  }}
 ]
}}

Remember, your goal is to create a compelling and visually interesting story that can be effectively illustrated through a storyboard. Be creative, consistent, and detailed in your scenario and prompts.
    """


def get_scenes_prompt(scenario_data: dict, num_scenes: int) -> str:
    scenario_text = scenario_data.get("scenario", "")
    language_name = scenario_data.get("language", {{}}).get("name", "English")
    style = scenario_data.get("style", "cinematic")
    characters_str = "\n".join(
        [
            f"""Name: {c.get("name", "")} 
Description: {c.get("description", "")} 
Voice Description: {c.get("voice", "")}"""
            for c in scenario_data.get("characters", [])
        ]
    )
    props_str = "\n".join(
        [
            f'{p.get("name", "")}\n\n{p.get("description", "")}'
            for p in scenario_data.get("props", [])
        ]
    )
    settings_str = "\n".join(
        [
            f'{s.get("name", "")}\n\n{s.get("description", "")}'
            for s in scenario_data.get("settings", [])
        ]
    )
    music_str = scenario_data.get("music", "")
    mood_str = scenario_data.get("mood", "")

    return f"""
    You are tasked with generating creative scenes for a short movie and creating prompts for storyboard illustrations. Follow these instructions carefully:
1. First, you will be given a scenario in {language_name}. This scenario will be the foundation for your storyboard.

<scenario>
{scenario_text}
</scenario>

<characters>
{characters_str}
</characters>

<props>
{props_str}
</props>

<settings>
{settings_str}
</settings>

<music>
{music_str}
</music>

<mood>
{mood_str}
</mood>

2. Generate exactly {num_scenes}, creative scenes to create a storyboard illustrating the scenario. Follow these guidelines for the scenes:
 a. For each scene, provide a JSON object with the keys: "imagePrompt", "videoPrompt", "description", "voiceover", and "charactersPresent".

3. The `imagePrompt` should be a JSON object for AI image generation for the first frame of the video, in {language_name}, with the style "{style}".

4. The `videoPrompt` should be a JSON object in {language_name}, focusing on movement and sound within the scene.

5. Format your entire output as a single JSON object with one key, "scenes", which contains a list of the {num_scenes} scene objects you generated.

Here is the required schema for your JSON output:
{{
  "scenes": [
    {{
      "imagePrompt": {{ ... }},
      "videoPrompt": {{ ... }},
      "description": "[A scene description explaining what happens]",
      "voiceover": "[A short, narrator voiceover text. One full sentence.]",
      "charactersPresent": "[An array list of names of characters visually present in the scene]"
    }}
  ]
}}

Remember, your goal is to create a compelling and visually interesting story that can be effectively illustrated through a storyboard. Be creative, consistent, and detailed in your prompts.
Remember, the number of scenes should be exactly {num_scenes}.
    """
