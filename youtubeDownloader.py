import yt_dlp
import os
import subprocess
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import re
import time  # Add this import
from flask_socketio import SocketIO
import json

# Konfigurasi logging
logging.basicConfig(level=logging.ERROR)
def sanitize_filename(filename):
    # Menghapus karakter yang tidak diizinkan pada sistem file
    return re.sub(r'[<>:"/\\|?*\s]+', '_', filename)

# Fungsi untuk sanitasi nama file dengan menambahkan angka jika sudah ada
def get_unique_filename(base_path):
    base, ext = os.path.splitext(base_path)
    counter = 1
    sanitized_base = sanitize_filename(base)  # Pastikan nama disanitasi
    new_path = f"{sanitized_base}{ext}"

    while os.path.exists(new_path):
        new_path = f"{sanitized_base}({counter}){ext}"
        counter += 1
    return new_path


# Function to safely delete file using subprocess
def delete_file(filepath):
    try:
        if os.name == 'nt':  # Windows
            subprocess.run(['del', '/f', '/q', filepath], shell=True, check=True)
        else:  # Unix/Linux/MacOS
            subprocess.run(['rm', '-f', filepath], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to delete file {filepath}: {e}")

# Add this function after delete_file function
def move_to_download(source_file):
    download_dir = 'download'
    os.makedirs(download_dir, exist_ok=True)
    filename = os.path.basename(source_file)
    destination = os.path.join(download_dir, filename)
    
    try:
        if os.name == 'nt':  # Windows
            subprocess.run(['move', '/Y', source_file, destination], shell=True, check=True)
        else:  # Unix/Linux/MacOS
            subprocess.run(['mv', source_file, destination], check=True)
        return destination
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to move file {source_file} to download folder: {e}")
        return source_file

# Add this function after move_to_download function
def rename_without_prefix(filepath):
    """Remove 'download_' prefix from filename."""
    try:
        directory = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        if filename.startswith('download_'):
            new_filename = filename[9:]  # remove 'download_' (9 characters)
            new_filepath = os.path.join(directory, new_filename)
            if os.name == 'nt':  # Windows
                subprocess.run(['ren', filepath, new_filename], shell=True, check=True)
            else:  # Unix/Linux/MacOS
                os.rename(filepath, new_filepath)
            return new_filepath
        return filepath
    except Exception as e:
        logging.error(f"Failed to rename file: {e}")
        return filepath

# Update convert_to_mp3 function
def convert_to_mp3(video_file, output_filename):
    try:
        os.system(f'ffmpeg -i "{video_file}" -q:a 0 -map a "{output_filename}"')
        delete_file(video_file)
        # Move the converted file to download folder
        final_path = move_to_download(output_filename)
        if os.path.exists(final_path):
            logging.info(f"Opening media player for: {final_path}")
            open_media_player(final_path)
        else:
            logging.error(f"File not found: {final_path}")
            return jsonify({'error': 'Failed to download the audio file.'}), 500
    except Exception as e:
        logging.error(f"Conversion failed: {e}")

# Fungsi untuk membuka video dengan media player
def open_media_player(filename):
    try:
        if os.name == 'nt':  # Windows
            if os.path.splitext(filename)[1].lower() == '.m4a':
                aimp_path = r"C:\Program Files\AIMP\AIMP.exe"
                if os.path.exists(aimp_path):
                    subprocess.Popen([aimp_path, filename])
                else:
                    logging.warning("AIMP not found, trying default player.")
                    subprocess.Popen(['wmplayer.exe', filename])  # Fallback to Windows Media Player
            else:
                os.startfile(filename)  # Default
        elif os.name == 'posix':  # macOS/Linux
            subprocess.call(['xdg-open', filename])
    except Exception as e:
        logging.error(f"Failed to open media player: {e}")


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:3000", "http://localhost:9696"])
# Update konfigurasi CORS untuk menangani pre-flight requests dengan lebih baik
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:3000", "http://localhost:9696"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Access-Control-Allow-Origin"],
        "expose_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True,
        "max_age": 600
    }
})

def get_file_creation_time(filepath):
    """Get file creation time."""
    return os.path.getctime(filepath)

def delete_matching_time_videos(reference_time, video_folder = 'videos'):
    """Delete files in folder with matching creation time."""
    try:
        for filename in os.listdir(video_folder):
            if filename.endswith('.mp4'):
                filepath = os.path.join(video_folder, filename)
                if abs(get_file_creation_time(filepath) - reference_time) < 20:  # 1 second tolerance
                    delete_file(filepath)
    except Exception as e:
        logging.error(f"Error deleting matching time videos: {e}")

def progress_hook(d):
    if d['status'] == 'downloading':
        try:
            # Calculate percentage
            if d.get('total_bytes'):
                percentage = (d['downloaded_bytes'] / d['total_bytes']) * 100
            elif d.get('total_bytes_estimate'):
                percentage = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
            else:
                percentage = 0
            
            # Get format information
            format_id = d.get('info_dict', {}).get('format_id', '')
            acodec = d.get('info_dict', {}).get('acodec', '')
            vcodec = d.get('info_dict', {}).get('vcodec', '')
            
            # Improved type detection
            download_type = 'unknown'
            if vcodec != 'none' and acodec == 'none':
                download_type = 'video'
            elif acodec != 'none' and vcodec == 'none':
                download_type = 'audio'
            
            print(f"Progress: {download_type} - {percentage}% - Format: {format_id} - Codecs: v={vcodec}, a={acodec}")
            
            # Only emit if we know the type
            if download_type != 'unknown':
                socketio.emit('download_progress', {
                    'type': download_type,
                    'percent': percentage
                })
            
        except Exception as e:
            logging.error(f"Error in progress_hook: {str(e)}")

@app.route('/fetch_formats', methods=['POST'])
def fetch_formats():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'Please enter a URL.'}), 400
    
    ydl_opts = {}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            global video_title
            video_title = re.sub(r'[<>:"/\\|?*\s]', '_', info.get('title', 'video')).replace('/', '_')  # Sanitasi nama file

            # Filter format video dengan resolusi yang jelas, tanpa bitrate premium
            available_resolutions = []
            for f in formats:
                if 'height' in f and f['ext'] == 'mp4':
                    resolution = f"{f['width']}x{f['height']}"
                    
                    # Hindari format dengan bitrate sangat tinggi (bitrate premium)
                    if f.get('vbr') and f['vbr'] > 5000:  # 5000 kbps sebagai batas bitrate premium
                        continue
                    
                    available_resolutions.append((resolution, f['format_id']))
            
            # Hilangkan resolusi duplikat
            available_resolutions = list(dict(available_resolutions).items())
            
            # Return available resolutions as a response
            return jsonify(available_resolutions)
    except Exception as e:
        return jsonify({'error': f"Failed to fetch formats: {e}"}), 500

@app.route('/download_video', methods=['POST'])
def download_video():
    url = request.json.get('url')
    format_id = request.json.get('format_id')
    convert_to_mp3_flag = request.json.get('convert_to_mp3', False)
    autoplay = request.json.get('autoplay', False)  # Add this parameter
    
    if not url or not format_id:
        return jsonify({'error': 'Please enter a URL and select a resolution.'}), 400
    
    if convert_to_mp3_flag:
        # Jika convert_to_mp3_flag True, download hanya audio m4a ke folder 'download'
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]',
            'outtmpl': os.path.join('download', f'{video_title}.%(ext)s'),
            'progress_hooks': [progress_hook],
        }
    else:
        ydl_opts = {
            'format': format_id,
            'outtmpl': os.path.join('videos', f'{video_title}.%(ext)s'),
            'progress_hooks': [progress_hook],
        }

    # Pastikan folder 'download' ada
    os.makedirs('download', exist_ok=True)

    def handle_media(file_path):
        try:
            if not os.path.exists(file_path):
                logging.error(f"File not found: {file_path}")
                return False
                
            # Tunggu sebentar untuk memastikan file tidak sedang digunakan
            time.sleep(1)
            
            if os.name == 'nt':  # Windows
                if os.path.splitext(file_path)[1].lower() == '.m4a':
                    aimp_path = r"C:\Program Files\AIMP\AIMP.exe"
                    if os.path.exists(aimp_path):
                        subprocess.Popen([aimp_path, file_path], creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        subprocess.Popen(['wmplayer.exe', file_path], creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    # Gunakan subprocess.Popen alih-alih os.startfile
                    subprocess.Popen(['cmd', '/c', 'start', '', file_path], 
                                   shell=True, 
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            elif os.name == 'posix':
                subprocess.Popen(['xdg-open', file_path], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            logging.error(f"Failed to open media player: {e}")
            return False

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)  # Langsung download
            if convert_to_mp3_flag:
                # Get the actual downloaded file path
                downloaded_file = ydl.prepare_filename(info)
                if os.path.exists(downloaded_file):
                    logging.info(f"File downloaded successfully: {downloaded_file}")
                    handle_media(downloaded_file)  # Replace direct open_media_player call
                    return jsonify({'message': 'Download completed successfully.'})
                else:
                    logging.error(f"File not found after download: {downloaded_file}")
                    return jsonify({'error': 'Failed to find downloaded file.'}), 500

            formats = info['formats']
            
            # Cek apakah ada format mp4 dengan codec mp4a.40.2
            mp4_with_audio = None
            video_only = None
            audio_m4a = None

            for f in formats:
                if f['format_id'] == format_id and f.get('acodec') == 'mp4a.40.2':
                    mp4_with_audio = f
                    break
                if f['format_id'] == format_id and f.get('vcodec') != 'none' and f.get('acodec') == 'none':
                    video_only = f
                if f.get('acodec') == 'mp4a.40.2' and f.get('vcodec') == 'none':
                    audio_m4a = f

            video_folder = 'videos'
            audio_folder = 'audios'
            download_folder = 'download'
            os.makedirs(video_folder, exist_ok=True)
            os.makedirs(audio_folder, exist_ok=True)
            os.makedirs(download_folder, exist_ok=True)
            
            output_filename = f'{video_title}.mp4'
            if convert_to_mp3_flag:
                # Download audio saja
                ydl.download([url])
                output_filename = get_unique_filename(ydl.prepare_filename(info))
                if os.path.exists(output_filename):
                    logging.info(f"Opening media player for: {output_filename}")
                    open_media_player(output_filename)
                else:
                    logging.error(f"File not found: {output_filename}")
                    return jsonify({'error': 'Failed to download the audio file.'}), 500
            else:
                if mp4_with_audio:
                    # Jika format mp4 dengan audio ada, unduh langsung
                    output_filename = get_unique_filename(os.path.join(video_folder, output_filename))
                    if os.path.exists(output_filename):
                        ydl.download([url])
                        if convert_to_mp3_flag:
                            convert_to_mp3(output_filename, get_unique_filename(os.path.join(video_folder, f'{video_title}.mp3')))
                        else:
                            handle_media(output_filename)  # Replace direct open_media_player call
                    else:
                        ydl.download([url])
                        if convert_to_mp3_flag:
                            convert_to_mp3(output_filename, get_unique_filename(os.path.join(video_folder, f'{video_title}.mp3')))
                        else:
                            handle_media(output_filename)  # Replace direct open_media_player call
                elif video_only and audio_m4a:
                    # Jika tidak ada, unduh video-only dan audio m4a, kemudian gabungkan
                    video_filename = get_unique_filename(os.path.join(video_folder, f'{video_title}.mp4'))
                    audio_filename = get_unique_filename(os.path.join(audio_folder, f'{video_title}.m4a'))

                    # Tambahkan informasi format ke options
                    ydl_opts_video = {
                        'format': video_only['format_id'],
                        'outtmpl': video_filename,
                        'progress_hooks': [progress_hook],
                        'format_note': 'video'  # Tambahkan ini
                    }
                    ydl_opts_audio = {
                        'format': audio_m4a['format_id'],
                        'outtmpl': audio_filename,
                        'progress_hooks': [progress_hook],
                        'format_note': 'audio'  # Tambahkan ini
                    }
                    
                    # Reset progress sebelum mulai
                    socketio.emit('download_progress', {'type': 'reset'})
                    
                    # Download video
                    print("Starting video download...")
                    with yt_dlp.YoutubeDL(ydl_opts_video) as ydl_video:
                        ydl_video.download([url])
                    
                    # Signal video complete
                    socketio.emit('download_progress', {'type': 'video', 'percent': 100})
                    
                    # Download audio
                    print("Starting audio download...")
                    with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl_audio:
                        ydl_audio.download([url])
                    
                    # Signal audio complete
                    socketio.emit('download_progress', {'type': 'audio', 'percent': 100})
                    
                    # Start merging
                    print("Starting merge process...")
                    socketio.emit('download_progress', {'type': 'merging', 'percent': 0})
                    
                    # Gabungkan menggunakan ffmpeg
                    output_filename = get_unique_filename(os.path.join(download_folder, f'{video_title}.mp4'))
                    os.system(f'ffmpeg -i "{video_filename}" -i "{audio_filename}" -c copy -f mp4 "{output_filename}"')
                    
                    # Signal merge complete
                    socketio.emit('download_progress', {'type': 'merging', 'percent': 100})

                    # Delete temporary files and move final output to download folder
                    delete_file(video_filename)
                    delete_file(audio_filename)
                    
                    # Get creation time of output file and delete matching videos
                    output_creation_time = get_file_creation_time(output_filename)
                    delete_matching_time_videos(output_creation_time)
                    
                    final_path = move_to_download(output_filename)
                    final_path = rename_without_prefix(final_path)  # Add this line
                    
                    # Tambahkan delay sebelum autoplay
                    time.sleep(2)  # Tunggu 2 detik
                    
                    if os.path.exists(final_path):
                        if autoplay:
                            success = handle_media(final_path)
                            if not success:
                                logging.warning("Autoplay failed, but download was successful")
                    else:
                        return jsonify({'error': 'Failed to create the final video.'}), 500
                        
                    socketio.emit('download_progress', {'type': 'complete', 'percent': 100})
                else:
                    return jsonify({'error': 'No suitable video or audio formats found.'}), 400
    except Exception as e:
        logging.error(f"Download failed: {str(e)}")
        socketio.emit('download_progress', {'type': 'error', 'message': str(e)})
        return jsonify({'error': f"Download failed: {str(e)}"}), 500

    # Return success message as a response
    return jsonify({'message': 'Download completed successfully.'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080)
