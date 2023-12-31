from dagster import Out, op
import requests
import os
import spotipy.util as util
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
from sqlalchemy import create_engine
from sp_etl.db_conn import postgres_connection
from configparser import ConfigParser
from airflow.providers.postgres.hooks.postgres import PostgresHook
import os
import hashlib
import boto3
from io import StringIO

config = ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__name__)), 'sp_etl/database.ini'))

client_id = config.get('sp_creds', 'client_id')
client_secret = config.get('sp_creds', 'client_secret')
username = config.get('sp_creds', 'username')
scope = "user-library-read"
redirect_uri = "http://localhost:7777/callback"

aws_access_key_id =  config.get('aws_creds', 'aws_access_key_id')
aws_secret_access_key = config.get('aws_creds', 'aws_secret_access_key')






@op(out={
    "artist_list_exploded": Out(),
    "song_list": Out(),
    "album_list": Out(),
    "artist_list": Out(),
    "track_features": Out(),
    "add": Out(),
    "track_ids": Out(),
    "artist_ids": Out(),
    "artist_id": Out(),
    "artist_list_new": Out(),
    "artists_by_id": Out(),
    "album_id_list": Out(),
    "release_date_list": Out(),
    "album_image_list": Out(),
    "genre_by_artists": Out()
})
def extract_spotify_liked_songs(context):
    limit = 20
    offset = 0
    all_items = []
    add = []
    artists_by_id = {}
    song_list =[]
    artist_list = []
    artist_id = []
    album_list=[]
    track_ids=[]
    track_features = []
    artist_list_new=[]
    release_date_list = []
    album_id_list =[]
    album_image_list = []
    auth_manager = SpotifyOAuth(client_id=client_id,
                                client_secret=client_secret,
                                redirect_uri=redirect_uri,
                                scope=scope)
    access_token = auth_manager.get_access_token(as_dict=False)
    print(access_token)
    # Get the authorization token for the user
    # access_token = util.prompt_for_user_token(username, scope, client_id, client_secret, redirect_uri)
    headers = {
    'Authorization': 'Bearer {}'.format(access_token)
    }
    response = requests.get('https://api.spotify.com/v1/me/tracks', headers=headers).json()
    total = response['total'] 
    context.log.info(f'{total} songs found')
    context.log.info(f'Processing {total} all songs')
    print("Total 'liked songs' found:", total)
    #total
    #print("Total 'liked songs' found:", total)
    for offset in range(0, total, 20):
        url = "https://api.spotify.com/v1/me/tracks?offset="+str(offset) + "&limit=20" 
        response1 = requests.get(url, headers=headers).json()
        getter = response1['items']
        all_items.extend(getter)
    print("Processing all", total ,"songs !!")
    try:
        for j in all_items:
            dateAddd = j['added_at'] 
            #dateAdd = dateAddd[0:10]#added date
            add.append(dateAddd)
            s_n = [j['track']['name']]
            Id = [j['track']['id']] #id
            identif = ' '.join(str(v) for v in Id) 
            track_ids.append(identif)
            song_name = ','.join(str(v) for v in s_n) 
            song_list.append(song_name) #tracks
            album = [j['track']['album']['name']]
            album1 = ' '.join(str(v) for v in album) 
            album_list.append(album1) #albums
            album_release_date = j['track']['album']['release_date']
            release_date_list.append(album_release_date)
            album_id = j['track']['album']['id']
            album_id_list.append(album_id)
            if j['track']['album']['images']:
                album_image = j['track']['album']['images'][0]['url']
                album_image_list.append(album_image)
            else:
                album_image_list.append(None)
            artists = j['track']['album']['artists']
            artist_names = []
            artist_list_exploded = []
            artist_ids = []
            for artist in artists:
                artist_names.append(artist['name'])
                artist_ids.append(artist['id'])
                if artist['id'] in artists_by_id:
                    if artist['name'] not in artists_by_id[artist['id']]:
                        artists_by_id[artist['id']].append(artist['name'])
                else:
                    artists_by_id[artist['id']] = [artist['name']]
            #artist_list.append(', '.join(artist_names)) 
            artist_list.append(artist_names)
            artist_id.append(artist_ids)    
        for artistid, artist_names in artists_by_id.items():
            artist_list_exploded.append(artistid)
            artist_list_new.append(artist_names)
        url = "https://api.spotify.com/v1/audio-features/"
        for i in track_ids:
            urls = url + i
            res = requests.get(urls, i, headers=headers).json()
            dance_score = [res['id'],res['danceability'], res['energy'],res['key']
            ,res['loudness'],res['mode'],res['speechiness'],res['acousticness']
            ,res['instrumentalness'],res['liveness'],res['valence'], res['tempo']]
            track_features.append(dance_score)
        genre_by_artists = []
        url2 = "https://api.spotify.com/v1/artists/" 
        for i in artist_list_exploded:
            genre_url = url2 + i
            response2 = requests.get(genre_url, headers=headers)
            if response2.status_code == 200:
                artist = response2.json()
                genre_by_artists.append(artist['genres'])
            else:
                print(f"Error: {response2.status_code}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        context.log.info("Extracted data from Spotify API.")
    return artist_list_exploded, song_list, album_list, \
        artist_list, track_features, add, track_ids, \
            artist_ids, artist_id, artist_list_new, artists_by_id, \
    album_id_list, release_date_list, album_image_list, genre_by_artists 
            






#Transformation


@op(out={
    "df_features":Out(),
    "distinct_genres":Out(),
    "df_album":Out(),
    "df_artists":Out(),
    "df_tracks":Out(),
    "df_track_artist_bridge":Out(),
    "df_artist_genres_bridge":Out(),
    "df_track_genre_bridge":Out(),
    "df_date":Out(),
    "df_grand_master":Out()
})
def dataframes_transform(context,artist_list_exploded, song_list, album_list, \
        artist_list, track_features, add, track_ids, \
            artist_ids, artist_id, artist_list_new, artists_by_id, \
    album_id_list, release_date_list, album_image_list, genre_by_artists):
    context.log.info("Data transformation initiated.")
    master_data = {'date_added': add,
            'track_id': track_ids,
            'song_name': song_list,
            'album_name': album_list,
            'ablum_id':album_id_list,
            'release_date':release_date_list,
            'cover_art':album_image_list,
            'artist': artist_list,
            'artist_id': artist_id
            }
    df_master = pd.DataFrame(master_data)
    ############################## track features ############################## 
    #fact_features
    df_features = pd.DataFrame(track_features)
    df_features.columns=['track_id','danceability','energy','key','loudness','mode'\
                        ,'speechiness','acousticness', 'instrumentalness','liveness','valence', 'tempo']
    #df_features.to_csv('d:/projects_de/spotify_dimensional_modeling/fact_track_features.csv')
    # merge master_data and df_features
    df_grand_master = pd.merge(df_master, df_features, on='track_id')
    #df_grand_master.to_csv('d:/projects_de/spotify_dimensional_modeling/great_master_data.csv', index=False)
    ############################## album ##############################
    #dim_album
    df_album = pd.DataFrame({"album_id": album_id_list, "album_name":album_list, "release_date": release_date_list, "cover_art": album_image_list})
    #df_album.to_csv('d:/projects_de/spotify_dimensional_modeling/dim_album.csv', index=False)
    ############################## artist ##############################
    #DIM_ARTISTS
    df_artists = pd.DataFrame({"artist_id": artist_list_exploded, "artist_name": artist_list_new})
    df_artists['artist_name'] = df_artists['artist_name'].str.join(', ')
    #df_artists.to_csv('d:/projects_de/spotify_dimensional_modeling/dim_artists.csv', index=False)
    #df_artists = df_artists.reset_index().rename(columns={'index': 'artist_key'})df_artists['artist_key'] += 1  # add 1 to the index values
    ############################## tracks ##############################
    #DIM_TRACKS
    df_tracks = pd.DataFrame({"track_id": track_ids, "album_id": album_id_list,"track_name": song_list, "album_name": album_list})
    #df_tracks = df_tracks.reset_index().rename(columns={'index': 'track_key'})df_tracks['track_key'] += 1  # add 1 to the index values
    #df_tacks.to_csv('d:/projects_de/spotify_dimensional_modeling/dim_tracks.csv', index=False)
    #explosion
    data = [(i, artist, artist_id) for i, row in df_master.iterrows() for artist, artist_id in zip(row['artist'], row['artist_id'])]
    df_exploded = pd.DataFrame(data, columns=['index', 'artist', 'artist_id']).set_index('index')
    df_master_exploded = pd.merge(df_master.drop(['artist', 'artist_id'], axis=1), df_exploded, left_index=True, right_index=True)
    ## creating a bridge table
    df_artist_track_bridge = df_master_exploded[['track_id', 'artist_id','song_name', 'artist']].drop_duplicates()
    #bridge_track_artist [bridge]
    df_track_artist_bridge = df_artist_track_bridge.drop(['song_name', 'artist'], axis=1)
    #df_artist_track_bridge.to_csv('d:/projects_de/spotify_dimensional_modeling/track_artist_prebridge.csv', index=False)
    #df_track_artist_bridge.to_csv('d:/projects_de/spotify_dimensional_modeling/fact_track_artist_bridge.csv', index=False)
    ############################## Genre ##############################
    df_artist_genres = pd.DataFrame({"artist_id":artist_list_exploded, "artist":artist_list_new, "genres":genre_by_artists})
    df_artist_genres['artist'] = df_artist_genres['artist'].str.join(', ')
    df_artist_genres = df_artist_genres.drop(['artist'], axis = 1)
    df_artist_genres = df_artist_genres.explode('genres').drop_duplicates()
    '''
    distinct_genres = df_artist_genres['genres'].unique()
    distinct_genres = pd.DataFrame(distinct_genres).dropna()
    distinct_genres.columns = ['genres']
    distinct_genres = distinct_genres.reset_index(drop=True)
    distinct_genres['genre_key'] = distinct_genres.index + 1
    '''
    #Distinct genres
    #dim_genre
    distinct_genres = df_artist_genres['genres'].unique()
    distinct_genres = pd.DataFrame(distinct_genres)
    distinct_genres.columns = ['genres']
    distinct_genres = distinct_genres.reset_index().rename(columns={'index': 'genre_key'})
    distinct_genres['genre_key'] += 1  # add 1 to the index values
    #df_artist_genres.to_csv('d:/projects_de/spotify_dimensional_modeling/dim_artist_genres.csv', index = False)
    #bridge_artist_genre [bridge]
    df_artist_genres_bridge = pd.merge(df_artist_genres, distinct_genres, on = 'genres').drop(['genres'], axis = 1)
    #bridge_track_genre [bridge]
    df_track_genre_bridge = pd.merge(df_track_artist_bridge, df_artist_genres_bridge, on = 'artist_id').drop(['artist_id'], axis = 1)
        ############################## DIM_DATE ##############################
    #dim_date
    df_date = pd.DataFrame({"datetime" : pd.to_datetime(add)})
    df_date["date_added"] = df_date["datetime"].dt.date
    df_date["time_added"] = df_date["datetime"].dt.time
    df_date['timezone'] = df_date['datetime'].dt.tz.zone
    df_date.insert(loc=0, column='track_id', value=track_ids) 
    df_date = df_date.reset_index().rename(columns={'index': 'date_key'})
    df_date['date_key'] += 1  # add 1 to the index values
    #df_date.to_csv('d:/projects_de/spotify_dimensional_modeling/dim_date.csv', index=False)
    '''
    distinct values of each columns of the df_tracks_genres df
    nunique = df_tracks_genres.nunique()
    # Display the number of distinct values for each column
    print(nunique)
    '''
    context.log.info("Data transformation completed.")
############################## S3Upload ##############################
    return df_features, distinct_genres, \
            df_album, df_artists, df_tracks, df_track_artist_bridge,\
                  df_artist_genres_bridge, \
        df_track_genre_bridge, df_date, df_grand_master


@op
def load_to_postgres(context, df_features, distinct_genres, \
            df_album, df_artists, df_tracks, df_track_artist_bridge,\
                  df_artist_genres_bridge, \
        df_track_genre_bridge, df_date):
    try:
        engine = postgres_connection()
    except Exception as e:
        print(f"Connection Uncessfull: {str(e)}")
    context.log.info("Loading has begun.")
    connection = engine.connect()
    connection.execute("drop table if exists master_sp.dim_details_large cascade;")
    #fact_track_features
    df_features.to_sql('fact_track_features', engine, schema='master_sp', if_exists='replace', index=False)
    #dim_genres
    distinct_genres.to_sql('dim_genres', engine, schema='master_sp', if_exists='replace', index=False)
    #dim_album
    df_album.to_sql('dim_album', engine, schema='master_sp', if_exists='replace', index=False)
    #dim_artists
    df_artists.to_sql('dim_artists', engine, schema='master_sp', if_exists='replace', index=False)
    #dim_tracks
    df_tracks.to_sql('dim_tracks', engine, schema='master_sp', if_exists='replace', index=False)
    #fact_track_artist_bridge
    df_track_artist_bridge.to_sql('track_artist_bridge', engine, schema='master_sp', if_exists='replace', index=False)
    #track_artist_prebridge
    df_artist_genres_bridge.to_sql('artist_genres_bridge', engine, schema='master_sp', if_exists='replace', index=False)
    #track_artist_prebridge
    df_track_genre_bridge.to_sql('track_genre_bridge', engine, schema='master_sp', if_exists='replace', index=False)
    #dim_date
    df_date.to_sql('dim_date', engine, schema='master_sp', if_exists='replace', index=False)
    context.log.info("load completed.") 


@op 
def s3_upload(context,df_grand_master):
    context.log.info("Loading has begun.")
    s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)

    # Set the name of your S3 bucket and the file path where you want to save the CSV file
    bucket_name = 's3numerone'
    file_path = 'master_data.csv'
    # Convert your dataframe to a CSV string
    csv_buffer = StringIO()
    df_grand_master.to_csv(csv_buffer, index=False)
    # Upload the CSV file to the S3 bucket
    s3.put_object(Body=csv_buffer.getvalue(), Bucket=bucket_name, Key=file_path)
    context.log.info("load completed.")

'''
client_id = os.environ.get("SP_CLIENT_ID")
client_secret = os.environ.get("SP_CLIENT_SECRET")

config = ConfigParser()
config.read(os.path.join(os.path.abspath(os.path.dirname(__name__)), 'database.ini'))

try:
    # Get Postgres connection details from config
    postgres_user = config.get('postgres', 'user')
    postgres_password = config.get('postgres', 'password')
    postgres_host = config.get('postgres', 'host')
    postgres_port = config.get('postgres', 'port')
    postgres_database = config.get('postgres', 'database')
    engine = create_engine(f'postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_database}')
    print("Connected to Postgres database successfully!")
except Exception as e:
    print("Failed to connect to Postgres database: ", e)

'''

'''

@op
def load_to_postgres(,df_original, df_date, df_artists_final, df_unique_genres, df_features):
    connection = engine.connect()
    connection.execute("drop table if exists master_sp.dim_details_large cascade;")
    #dim_everythin_part_one
    df_original.to_sql('dim_details_small', engine, schema='master_sp', if_exists='replace', index=False)
    #dim_date
    df_date.to_sql('dim_date', engine, schema='master_sp', if_exists='replace', index=False)
    #dim_track_artists
    df_artists_final.to_sql('dim_track_artists', engine, schema='master_sp', if_exists='replace', index=False)
    #dim_genres
    df_unique_genres.to_sql('dim_track_genres', engine, schema='master_sp', if_exists='replace', index=False)
    #fact_artist
    df_features.to_sql('fact_track_features', engine, schema='master_sp', if_exists='replace', index=False)
    .log.info("load completed.")


    

limit = 20
offset = 0
all_items = []
add = []
artists_by_id = {}
song_list =[]
artist_list = []
artist_id = []
album_list=[]
track_ids=[]
genre_list = []
track_features = []
artist_list_new=[]
auth_manager = SpotifyOAuth(client_id=client_id,
        client_secret=client_secret,
           redirect_uri=redirect_uri,
           scope=scope)
access_token = auth_manager.get_access_token(as_dict=False)
headers = {
    'Authorization': 'Bearer {}'.format(access_token)
}
response = requests.get('https://api.spotify.com/v1/me/tracks', headers=headers).json()
total = response['total']
#total
print("Total 'liked songs' found:", total)

for offset in range(0, total, 20):
    url = "https://api.spotify.com/v1/me/tracks?offset="+str(offset) + "&limit=20" 
    response1 = requests.get(url, headers=headers).json()
    getter = response1['items']
    all_items.extend(getter)

for j in all_items:
    dateAddd = j['added_at'] 
        #dateAdd = dateAddd[0:10]#added date
    add.append(dateAddd)
    s_n = [j['track']['name']]
    Id = [j['track']['id']] #id
    identif = ' '.join(str(v) for v in Id) 
    track_ids.append(identif)
    song_name = ','.join(str(v) for v in s_n) 
    song_list.append(song_name) #tracks
    album = [j['track']['album']['name']]
    album1 = ' '.join(str(v) for v in album) 
    album_list.append(album1) #albums
    artists = j['track']['album']['artists']
    artist_names = []
    artist_ids = []
    artist_genres = set()
    
for artist in artists:
    artist_names.append(artist['name'])
    artist_ids.append(artist['id'])
    if artist['id'] in artists_by_id:
        if artist['name'] not in artists_by_id[artist['id']]:
            artists_by_id[artist['id']].append(artist['name'])
    else:
        artists_by_id[artist['id']] = [artist['name']]
    url = "https://api.spotify.com/v1/artists/" + artist['id']
    response2 = requests.get(url, headers=headers)
    
if response2.status_code == 200:
    artist = response2.json()
    g_n = artist['genres']
    artist_genres.update(g_n)
else:
    print(f"An error occurred: {str(e)}")

if hasattr(response2, 'status_code'):
    if response2.status_code == 200:
        artist = response2.json()
        g_n = artist['genres']
        artist_genres.update(g_n)
    elif response2.status_code == 429:
        print("Error: Too many requests")
    else:
        print(f"Error: {response2.status_code}")
else:
    print("Error: Unable to retrieve artist information")



artist_list.append(', '.join(artist_names)) #artist name
genre_list.append(list(artist_genres))    





for artistid, artist_names in artists_by_id.items():
    artist_id.append(artistid)
    artist_list_new.append(artist_names)

while len(genre_list) < len(song_list):
    genre_list.append([])# Ensure that the genre list has the same number of records as the other lists


url = "https://api.spotify.com/v1/audio-features/"

for i in track_ids:
    urls = url + i
    res = requests.get(urls, i, headers=headers).json()
    dance_score = [res['id'],res['danceability'], res['energy'],res['key']
    ,res['loudness'],res['mode'],res['speechiness'],res['acousticness']
    ,res['instrumentalness'],res['liveness'],res['valence'], res['tempo']]
    track_features.append(dance_score)








except Exception as e:
    print(f"An error occurred: {str(e)}")
return song_list, album_list, genre_list, track_features, add, track_ids, artist_id, artist_list_new
'''  
'''

@op(out={"df_original":  Out(),
         "df_date":  Out(),
         "df_artists_final":  Out(),
         "df_unique_genres":  Out(),
         "df_features":  Out()})
def dataframes_transform(,song_list, album_list, genre_list, track_features, add, track_ids, artist_id, artist_list_new):
    df_original = pd.DataFrame({"track_id": track_ids,"track_list":song_list,"album_name" : album_list})
    ##Date###manipulating date and time    
    df_date = pd.DataFrame({"datetime" : pd.to_datetime(add)})
    df_date["date_added"] = df_date["datetime"].dt.date
    df_date["time_added"] = df_date["datetime"].dt.time
    df_date['timezone'] = df_date['datetime'].dt.tz.zone
    df_date.insert(loc=0, column='track_id', value=track_ids) # Add the 'id' column to df_artists
    df_date["datetime_track_id"] = df_date["datetime"].astype(str) + "_" + df_date["track_id"].astype(str)
    df_date["datetime_track_id_hash"] = df_date["datetime_track_id"].apply(lambda x: hashlib.sha256(x.encode()).hexdigest())
    df_date = df_date.drop(columns=['datetime_track_id'])
    df_date.set_index("datetime_track_id_hash", inplace=True)
    .log.info("Transformed DATE")
    ###artist##
    #separating the artists and merging the df_artist to final-1 df
    df_artistsid = pd.DataFrame({"artist_id": artist_id })
    df_artistsid = df_artistsid.explode('artist_id').reset_index(drop=True)
    unique_artistsid = df_artistsid['artist_id'].unique()
    df_unique_artistsid = pd.DataFrame({'artist_unique_id': unique_artistsid})
    df_artists = pd.DataFrame({"artist_name":artist_list_new })
    #df_artists['artist_name'] = df_artists['artist_name'].str.split(',')
    df_artists = df_artists.explode('artist_name').reset_index(drop=True)
    unique_artistname = df_artists['artist_name'].unique()
    df_unique_artistname = pd.DataFrame({'artist_unique_name': unique_artistname})
    df_artists_final = pd.concat([df_unique_artistsid, df_unique_artistname], axis=1)
    .log.info("Transformed ARTISTS")
    #####################genre#######################
    #add columns to df_genre(separate table for genre)
    #max colmns
    df_genre_all = pd.DataFrame({"genre":genre_list})
    df_genre_all = df_genre_all.explode('genre').reset_index(drop=True)
    unique_genres = df_genre_all['genre'].unique()
    df_unique_genres = pd.DataFrame({'genre': unique_genres})
    .log.info("Transformed GENRES")
    #df_unique_genres.insert(loc=0, column='track_name', value=e.song_list) # Add the 'id' column to df_artists
    #(separate table for features)
    df_features = pd.DataFrame(track_features)
    df_features.columns=['track_id','danceability','energy','key','loudness','mode','speechiness',\
                         'acousticness', 'instrumentalness','liveness','valence', 'tempo']
    .log.info("Transformed FEATURES")
    .log.info("Transformed completed.")
    #df_features.insert(loc=0, column='track_list', value=song_list) # Add the 'id' column to df_artists
    yield Output(df_original, "df_original")
    yield Output(df_date, "df_date")
    yield Output(df_artists_final, "df_artists_final")
    yield Output(df_unique_genres, "df_unique_genres")
    yield Output(df_features, "df_features")


'''















