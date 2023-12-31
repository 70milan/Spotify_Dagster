from dagster import job, op

from sp_etl.ops.dag_main import extract_spotify_liked_songs,\
    dataframes_transform,load_to_postgres,s3_upload

@job
def run_etl_job():
    artist_list_exploded, song_list, album_list, \
        artist_list, track_features, add, track_ids, \
            artist_ids, artist_id, artist_list_new, artists_by_id, \
    album_id_list, release_date_list, album_image_list, genre_by_artists = extract_spotify_liked_songs()
    df_features, distinct_genres, \
            df_album, df_artists, df_tracks, df_track_artist_bridge,\
                  df_artist_genres_bridge, \
        df_track_genre_bridge, df_date, df_grand_master = dataframes_transform(
        artist_list_exploded=artist_list_exploded,
        song_list=song_list,
        album_list=album_list,
        artist_list=artist_list,
        track_features=track_features,
        add=add,
        artist_ids = artist_ids,
        track_ids=track_ids,
        artist_id=artist_id,
        artist_list_new=artist_list_new,
        artists_by_id=artists_by_id,
        album_id_list=album_id_list,
        release_date_list=release_date_list,
        album_image_list=album_image_list,
        genre_by_artists=genre_by_artists
    )
    load_to_postgres(df_features, distinct_genres, \
            df_album, df_artists, df_tracks, df_track_artist_bridge,\
                  df_artist_genres_bridge, \
        df_track_genre_bridge, df_date)
    s3_upload(df_grand_master)





 






'''





@op(ins={
    "song_list": In(),
    "album_list": In(),
    "genre_list": In(),
    "track_features": In(),
    "add": In(),
    "track_ids": In(),
    "artist_id": In(),
    "artist_list_new": In()
})
def dataframes_transform(context,song_list, album_list, genre_list, track_features, add, track_ids, artist_id, artist_list_new):
    context.log.info("Data transformation initiated.")
    #code
    return df_original, df_date, df_artists_final, df_unique_genres, df_features

@op
def load_to_postgres(context,df_original, df_date, df_artists_final, df_unique_genres, df_features):
    engine = postgres_connection()
    context.log.info("Loading has begun.")
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
    context.log.info("load completed.")
    
@graph
def my_pipeline():
    song_list, album_list, genre_list, track_features, add, track_ids, artist_id, artist_list_new = extract_spotify_liked_songs()
    dataframes_transform(song_list=song_list,
                   album_list=album_list,
                   genre_list=genre_list,
                   track_features=track_features,
                   add=add,
                   track_ids=track_ids,
                   artist_id=artist_id,
                   artist_list_new=artist_list_new)





    return song_list, album_list, artist_list, genre_list, track_features, add, track_ids, artist_ids, artist_id, artist_genres, artist_list_new, artists_by_id
    


    '''