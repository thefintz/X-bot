from datetime import datetime # so p horario, remover depois
import os
import tweepy

api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")
bearer_token = os.getenv("BEARER_TOKEN")
access_token = os.getenv("ACCESS_TOKEN")
access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

client = tweepy.Client(bearer_token, api_key, api_secret, access_token, access_token_secret)
auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
api = tweepy.API(auth)

current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # horario so p deixar o tweet unico pois n pode ser igual 2x em curto periodo
client.create_tweet(text=f"Hi X! Time: {current_time}")
