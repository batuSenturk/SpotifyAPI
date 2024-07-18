from flask import Flask, request, redirect, session, render_template, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import random

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'

client_id = '3d9ed14a89544679834d4ecefd26039d'
client_secret = '3cd8ae220b14410c8d7127196adf8ec2'
redirect_uri = 'http://localhost:8888/callback'

sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope='user-library-read user-top-read playlist-modify-public playlist-modify-private'
)

def get_all_playlists(sp):
    playlists = []
    results = sp.current_user_playlists()
    playlists.extend(results['items'])
    while results['next']:
        results = sp.next(results)
        playlists.extend(results['items'])
    return playlists

def get_recommendations(sp, track_id='3n3Ppam7vgaVa1iaRUc9Lp'):
    recommendations = sp.recommendations(seed_tracks=[track_id], limit=10)
    return recommendations['tracks']

@app.route('/')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect('/home')

@app.route('/home')
def home():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    sp = spotipy.Spotify(auth=token_info['access_token'])
    user = sp.current_user()
    return render_template('index.html', user=user)

@app.route('/top_tracks_artists')
def top_tracks_artists():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    sp = spotipy.Spotify(auth=token_info['access_token'])
    try:
        top_tracks = sp.current_user_top_tracks(limit=10)['items']
        top_artists = sp.current_user_top_artists(limit=10)['items']
        top_tracks_with_images = [
            {
                'rank': i+1,
                'name': track['name'],
                'artist': track['artists'][0]['name'],
                'image': track['album']['images'][0]['url']
            }
            for i, track in enumerate(top_tracks)
        ]
        top_artists_with_images = [
            {
                'rank': i+1,
                'name': artist['name'],
                'image': artist['images'][0]['url']
            }
            for i, artist in enumerate(top_artists)
        ]
        return render_template('top_tracks_artists.html', top_tracks=top_tracks_with_images, top_artists=top_artists_with_images)
    except Exception as e:
        return f"Error fetching top tracks and artists: {e}"

@app.route('/playlists')
def playlists():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    sp = spotipy.Spotify(auth=token_info['access_token'])
    try:
        playlists = get_all_playlists(sp)
        playlists_info = []
        for playlist in playlists:
            playlists_info.append(f"{playlist['name']} - {playlist['tracks']['total']} tracks")
        return render_template('playlists.html', playlists=playlists_info)
    except Exception as e:
        return "Error fetching playlists"

@app.route('/recommendations')
def recommendations():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    sp = spotipy.Spotify(auth=token_info['access_token'])
    try:
        seed_tracks = ['3n3Ppam7vgaVa1iaRUc9Lp']  # Example track ID
        recommendations = get_recommendations(sp, seed_tracks[0])
        playlists = get_all_playlists(sp)

        return render_template('recommendations.html', recommendations=recommendations, playlists=playlists, selected_playlist_id=playlists[0]['id'])
    except Exception as e:
        return f"Error fetching recommendations: {e}"

@app.route('/get_recommendations', methods=['POST'])
def get_recommendations_route():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    sp = spotipy.Spotify(auth=token_info['access_token'])
    track_id = request.form.get('track_id', '3n3Ppam7vgaVa1iaRUc9Lp')  # Default track ID if none provided
    try:
        recommendations = get_recommendations(sp, track_id)
        playlists = get_all_playlists(sp)

        return render_template('recommendations.html', recommendations=recommendations, playlists=playlists, selected_playlist_id=playlists[0]['id'])
    except Exception as e:
        return f"Error fetching recommendations: {e}"

@app.route('/add_to_playlist', methods=['POST'])
def add_to_playlist():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    sp = spotipy.Spotify(auth=token_info['access_token'])
    playlist_id = request.form['playlist_id']
    track_id = request.form['track_id']
    try:
        sp.user_playlist_add_tracks(user=sp.current_user()['id'], playlist_id=playlist_id, tracks=[track_id])
        # Get a new recommendation to replace the added song
        new_recommendations = sp.recommendations(seed_tracks=[track_id], limit=1)
        new_song = new_recommendations['tracks'][0]
        return jsonify({'status': 'success', 'new_song': new_song})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/save_playlist', methods=['POST'])
def save_playlist():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    sp = spotipy.Spotify(auth=token_info['access_token'])
    track_ids = request.form['track_ids'].strip(',').split(',')
    playlist_name = request.form['playlist_name']
    try:
        user_id = sp.current_user()['id']
        new_playlist = sp.user_playlist_create(user=user_id, name=playlist_name)
        sp.user_playlist_add_tracks(user=user_id, playlist_id=new_playlist['id'], tracks=track_ids)
        return redirect('/home')
    except Exception as e:
        return f"Error saving playlist: {e}"
    
@app.route('/refresh_recommendations', methods=['GET'])
def refresh_recommendations():
    token_info = session.get('token_info', None)
    if not token_info:
        return jsonify({'status': 'error', 'message': 'Token not found'})
    sp = spotipy.Spotify(auth=token_info['access_token'])
    try:
        seed_tracks = ['3n3Ppam7vgaVa1iaRUc9Lp']  # Example track ID
        recommendations = get_recommendations(sp, seed_tracks[0])
        recommendations_info = []
        for track in recommendations:
            recommendations_info.append({
                'id': track['id'],
                'name': track['name'],
                'artists': [{'name': artist['name']} for artist in track['artists']]
            })
        return jsonify({'status': 'success', 'recommendations': recommendations_info})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/recently_played')
def recently_played():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    sp = spotipy.Spotify(auth=token_info['access_token'])
    try:
        recently_played = sp.current_user_recently_played(limit=10)['items']
        return render_template('recently_played.html', recently_played=recently_played)
    except Exception as e:
        return f"Error fetching recently played tracks: {e}"

if __name__ == '__main__':
    app.run(port=8888)