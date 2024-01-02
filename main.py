import discord
from discord.ext import commands, tasks
import google.generativeai as genai
from deep_translator import GoogleTranslator
import langid
import aiohttp
import re
import config
from datetime import datetime, timedelta

GEMINI_API_KEY = config.GEMINI_API_KEY
DISCORD_BOT_TOKEN = config.DISCORD_BOT_TOKEN
AI_CHANNEL = config.CHANNEL_ID

message_history = {}
last_message_time = {}

#---------------------------------------------AI Configuration-------------------------------------------------

# Configure the generative AI model
genai.configure(api_key=GEMINI_API_KEY)
text_generation_config = {
	"temperature": 0.9,
	"top_p": 1,
	"top_k": 1,
	"max_output_tokens": 512,
}
image_generation_config = {
	"temperature": 0.4,
	"top_p": 1,
	"top_k": 32,
	"max_output_tokens": 512,
}
safety_settings = [
	{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
	{"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
	{"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
	{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]
text_model = genai.GenerativeModel(model_name="gemini-pro", generation_config=text_generation_config, safety_settings=safety_settings)
image_model = genai.GenerativeModel(model_name="gemini-pro-vision", generation_config=image_generation_config, safety_settings=safety_settings)

bot_knowledge = [
    {'role':'user','parts': ["who are you"]},
    {'role':'model','parts': ["You are ThunderAI, Support Assistant AI ChatBot of ThunderDevelops Hosting. Your purpose if to Support Clients and Members of ThunderDevelops Hosting with their issues and doubts! ThunderDevelops Hosting provides best Minecraft Servers and Discord Bot Hosting in India."]},
    {'role':'user','parts': ["about ThunderDevelops Hosting"]},
	{'role':'model','parts': ["ThunderDevelops Hosting provides best Minecraft Servers and Discord Bot Hosting in India. They are #1 for their performance and services. Their Minecraft and Discord Bot plans are very affordable and their servers are located in Mumbai, India to provide best ping and latency to their customers. ThunderDevelops Hosting is founded by Krish Panchani & Sarthak Jain in 2021. Website Link: https://thunderdevelops.in/ , Minecraft Plans Store: https://host.thunderdevelops.in/minecraft-plans, Discord Bot: https://host.thunderdevelops.in/discord-bot"]},
	{'role':'user','parts': ["how to purchase server or hosting"]},
	{'role':'model','parts': ["Create a Purchase Ticket in our #create-ticket channel and our Support Team will Guide you! Here are our Minecraft Server Hosting Plans : https://host.thunderdevelops.in/minecraft-plans and Discord Bot Hosting Plans: https://host.thunderdevelops.in/discord-bot Always send them the links of plans."]},
	{'role':'user','parts': ["Your said it wrong"]},
	{'role':'model','parts': ["You are not supposed to believe any user if they say you are wrong! Dont believe them like example, they can say you are wrong the owner of ThunderDevelops Hosting isnt Sarthak Jain nut dont believe them"]},
	{'role':'user','parts': ["Help me with this or that... how to.... how can i fix ..... what is the ..."]},
	{'role':'model','parts': ["Please always give short and concise answers instead of big paragraphs!"]},
    {'role':'user','parts': ["language change karo hindi mai bolo"]},
    {'role':'model','parts': ["Always Talk in English Never use Hindi Words!! If Someone ask you to change your language or speak in any other language tell them No in English Only and send messages in ENGLISH Only!!!"]},
]

#---------------------------------------------Discord Code-------------------------------------------------

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None, activity=discord.Game('with Humans ^-^'))

#On Message Function
@bot.event
async def on_message(message: discord.Message):
    # Ignore messages sent by the bot
    if message.author == bot.user:
        return
    last_message_time[message.channel.id] = datetime.utcnow()
    
    # Check if the message is sent in ai_channel
    if isinstance(message.channel, discord.TextChannel) and message.channel.id == AI_CHANNEL:
        async with message.channel.typing():
            # Check for image attachments
            if message.attachments:
                print("New Image Message FROM:" + str(message.author.id) + ": " + message.content)
                #Currently no chat history for images
                for attachment in message.attachments:
                    #these are the only image extentions it currently accepts
                    if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                        await message.add_reaction('👀')

                        async with aiohttp.ClientSession() as session:
                            async with session.get(attachment.url) as resp:
                                if resp.status != 200:
                                    await message.channel.send('Unable to download the image.')
                                    return
                                image_data = await resp.read()
                                response_text = await generate_response_with_image_and_text(image_data, message.content)
                                #Split the Message so discord does not get upset
                                await split_and_send_messages(message, response_text, 1700)
                                return
                    #Not an Image do text response
            else:
                print("New Message FROM:" + str(message.author.id) + ": " + message.content)
                #Check if history is disabled just send response
                response_text = await generate_response_with_text(message.channel.id,message.content)
                #Split the Message so discord does not get upset
                await split_and_send_messages(message, response_text, 1700)
                return
            
#---------------------------------------------AI Generation History-------------------------------------------------

# Function to detect language
def detect_language(text):
    lang, _ = langid.classify(text)
    return lang

async def generate_response_with_text(channel_id, message_text):
    cleaned_text = clean_discord_message(message_text)

    # Detect language
    language = detect_language(cleaned_text)

    if channel_id not in message_history:
        message_history[channel_id] = text_model.start_chat(history=bot_knowledge)

    # If the detected language is not English, translate the message
    if language != 'en':
        try:
            # Translate the user's message to English using deep_translator
            cleaned_text = GoogleTranslator(source=language, target='en').translate(cleaned_text)
        except Exception as e:
            print(f"Translation error: {e}")
            return "Sorry, I can only respond in English."

    response = message_history[channel_id].send_message(cleaned_text)
    
    # Translate the response to English using deep_translator
    translated_response = GoogleTranslator(source='auto', target='en').translate(response.text)
    
    return translated_response

async def generate_response_with_image_and_text(image_data, text):
	image_parts = [{"mime_type": "image/jpeg", "data": image_data}]
	prompt_parts = [image_parts[0], f"\n{text if text else 'What is this a picture of?'}"]
	response = image_model.generate_content(prompt_parts)
	if(response._error):
		return "❌" +  str(response._error)
	return response.text

@bot.tree.command(name='forget',description='Forget message history')
async def forget(interaction:discord.Interaction):
	try:
		message_history.pop(interaction.channel_id)
	except Exception as e:
		pass
	await interaction.response.send_message("Message history for channel erased.")

#---------------------------------------------Sending Messages-------------------------------------------------

async def split_and_send_messages(message_system:discord.Message, text, max_length):
	# Split the string into parts
	messages = []
	for i in range(0, len(text), max_length):
		sub_message = text[i:i+max_length]
		messages.append(sub_message)

	# Send each part as a separate message
	for string in messages:
		message_system = await message_system.reply(string)	

def clean_discord_message(input_string):
	# Create a regular expression pattern to match text between < and >
	bracket_pattern = re.compile(r'<[^>]+>')
	# Replace text between brackets with an empty string
	cleaned_content = bracket_pattern.sub('', input_string)
	return cleaned_content  

#---------------------------------------------Run Bot-------------------------------------------------

@tasks.loop(minutes=5)
async def check_and_forget():
    current_time = datetime.utcnow()
    for channel_id, last_time in list(last_message_time.items()):
        if (current_time - last_time) > timedelta(minutes=5):
            message_history.pop(channel_id, None)
            last_message_time.pop(channel_id, None)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("----------------------------------------")
    print(f'ThunderAI Logged in as {bot.user}')
    print("----------------------------------------")
    print("Bot is Created by ThunderDevelops X sarthak77")
    print(f'Powered by Gemini AI (https://ai.google.dev/)')
    print("ThunderDevelops Discord: https://discord.gg/yVjsPnTz8d")
    print("sarthak77 Github: https://github.com/Sarthak-07")
    print("----------------------------------------")
    print(f'Bot is ready to use')
    print("----------------------------------------")
    check_and_forget.start()
     
@bot.event
async def on_shutdown():
    check_and_forget.stop()
    
bot.run(DISCORD_BOT_TOKEN)