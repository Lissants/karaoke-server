import os
import json
import tempfile
import subprocess
import sys
from math import log2, sqrt
import numpy as np
from appwrite.client import Client
from appwrite.services.storage import Storage
from appwrite.services.databases import Databases
from scipy.io import wavfile
from dotenv import load_dotenv
from appwrite.query import Query
import datetime
from crepe import predict as crepe_predict
import tempfile
from collections import defaultdict

# Load environment variables early
load_dotenv('endpoints.env')

# Standard note frequency table
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def check_ffmpeg():
    # Try common FFmpeg paths
    for ffmpeg_path in ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg']:
        try:
            subprocess.run([ffmpeg_path, '-version'], check=True, capture_output=True)
            print(f"FFmpeg found at: {ffmpeg_path}")
            return True
        except Exception:
            continue
    
    print("FFmpeg check failed: Could not find FFmpeg in common locations")
    return False

if not check_ffmpeg():
    sys.exit(1)

def generate_note_frequencies():
    frequencies = {}
    for octave in range(0, 9):
        for i, note in enumerate(NOTE_NAMES):
            freq = 16.35 * (2 ** ((i + (octave * 12)) / 12))  # Added missing parenthesis here
            frequencies[f"{note}{octave}"] = round(freq, 2)
    return frequencies

NOTE_FREQUENCIES = generate_note_frequencies()

def frequency_to_note(freq):
    return min(NOTE_FREQUENCIES.items(), key=lambda x: abs(x[1] - freq))[0] if freq > 0 else None

def convert_audio_to_wav(input_path, output_path):
    try:
        input_path = os.path.abspath(input_path)
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        cmd = ['ffmpeg', '-y', '-i', input_path, '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '44100', output_path]
        if os.name == 'nt':
            cmd = f'ffmpeg -y -i "{input_path}" -acodec pcm_s16le -ac 1 -ar 44100 "{output_path}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0 or not os.path.exists(output_path):
            raise Exception(result.stderr or "Output file not created")
        return True
    except Exception as e:
        print(f"Conversion failed: {str(e)}")
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)
        return False

def download_and_process_audio(storage, file_id):
    try:
        # Use /tmp which is standard in containers
        temp_dir = "/tmp/karaoke_temp"
        os.makedirs(temp_dir, exist_ok=True)
        os.chmod(temp_dir, 0o777)  # Ensure writable
        print(f"Temp dir: {temp_dir}, Contents: {os.listdir(temp_dir)}")
        
        input_path = os.path.join(temp_dir, f"{file_id}.m4a")
        output_path = os.path.join(temp_dir, f"{file_id}.wav")

        # Download file
        print(f"Downloading file {file_id} from Appwrite storage")
        file_content = storage.get_file_download(os.getenv('APPWRITE_STORAGE_ID'), file_id)
        with open(input_path, 'wb') as f:
            f.write(file_content)
        print(f"Downloaded {os.path.getsize(input_path)} bytes to {input_path}")

        # Convert and process
        print(f"Converting {input_path} to WAV format")
        if not convert_audio_to_wav(input_path, output_path):
            raise Exception("Audio conversion failed")
            
        print(f"Reading WAV file from {output_path}")
        sr, audio = wavfile.read(output_path)
        print(f"Audio stats - SR: {sr}, Shape: {audio.shape}, Max: {np.max(audio)}, Min: {np.min(audio)}")

        max_samples = 30 * sr  # 30 seconds
        audio = audio[:max_samples] if len(audio) > max_samples else audio
        
        if len(audio) == 0:
            raise ValueError("Empty audio file")

        print(f"Starting CREPE processing for {file_id}")
        try:
            time, frequency, confidence, _ = crepe_predict(
                audio, 
                sr, 
                model_capacity='tiny',  # Start with tiny model first
                viterbi=True,
                step_size = 50,
                center = False
            )
            print(f"CREPE results - time: {len(time)}, freq: {len(frequency)}, conf: {len(confidence)}")
            print("CREPE processing completed successfully")
        except Exception as e:
            print(f"CREPE processing failed: {str(e)}")
            raise
        
        # Clean up
        os.remove(input_path)
        os.remove(output_path)
        
        return time, frequency, confidence
    except Exception as e:
        print(f"Error processing {file_id}: {str(e)}")
        if 'input_path' in locals() and os.path.exists(input_path):
            os.remove(input_path)
        if 'output_path' in locals() and os.path.exists(output_path):
            os.remove(output_path)
        raise

def calculate_performance(frequencies, confidences):
    valid_freqs = frequencies[confidences > 0.5]
    return {frequency_to_note(freq): 1 - 12 * abs(log2(freq/NOTE_FREQUENCIES[frequency_to_note(freq)]))
            for freq in valid_freqs if frequency_to_note(freq)}

def process_recordings(databases, storage, document_ids):
    combined_performance = defaultdict(lambda: {"sum": 0, "count": 0})
    processed_files = []
    
    for doc_id in document_ids:
        try:
            print(f"Processing document {doc_id}")
            doc = databases.get_document(
                os.getenv('APPWRITE_DB_ID'),
                os.getenv('APPWRITE_USER_TRACKS_COLLECTION_ID'),
                doc_id
            )
            
            if not doc.get('fileIds'):
                print(f"No fileIds found in document {doc_id}")
                continue
                
            file_id = doc['fileIds'][0]
            print(f"Found fileId {file_id} in document")
            time, frequency, confidence = download_and_process_audio(storage, file_id)
            performance = calculate_performance(frequency, confidence)
            
            for note, score in performance.items():
                combined_performance[note]["sum"] += score
                combined_performance[note]["count"] += 1
                
            processed_files.append(file_id)
            print(f"Successfully processed {file_id}")
        except Exception as e:
            print(f"Error processing {doc_id}: {str(e)}")
            
    return {
        note: entry["sum"] / entry["count"]
        for note, entry in combined_performance.items()
    }, processed_files

def generate_recommendations(tracks, performance):
    recommendations = []
    for track in tracks:
        try:
            
            print(f"Generating recommendations from {len(tracks)} tracks")
            print(f"User performance metrics: {len(performance)} notes")
            
            # Handle different note data formats
            notes_data = track.get('notesBinary', {})
            
            # Case 1: Already a dictionary
            if isinstance(notes_data, dict):
                binary_notes = notes_data
            # Case 2: JSON string
            elif isinstance(notes_data, str):
                binary_notes = json.loads(notes_data)
            # Case 3: List format
            elif isinstance(notes_data, list):
                binary_notes = {note: 1 for note in notes_data}
            else:
                binary_notes = {}
            
            # Calculate similarity
            valid_notes = [note for note in binary_notes if binary_notes.get(note) == 1]
            if not valid_notes:
                continue
                
            distance = sqrt(sum((1 - performance.get(note, 0))**2 for note in valid_notes)) / len(valid_notes)
            
            recommendations.append({
                'id': track['$id'],
                'songName': track['songName'],
                'artist': track['artist'],
                'similarity': 1 - distance,
                'genre': track['genre']
            })
            
        except Exception as e:
            print(f"Error processing track {track.get('$id')}: {str(e)}")
            continue
    
    return sorted(recommendations, key=lambda x: x['similarity'], reverse=True)[:5]

def main(data: dict):
    """Redesigned main function to work with direct dictionary input"""
    document_id = data['documentId']
    file_ids = data['fileIds']
    user_id = data['userId']
    
    try:
        # Initialize Appwrite client
        client = Client()
        client.set_endpoint(os.getenv('APPWRITE_ENDPOINT'))
        client.set_project(os.getenv('APPWRITE_PROJECT_ID'))
        client.set_key(os.getenv('APPWRITE_API_KEY'))
        
        databases = Databases(client)
        storage = Storage(client)

        # Update status to processing
        databases.update_document(
            os.getenv('APPWRITE_DB_ID'),
            os.getenv('APPWRITE_USER_TRACKS_COLLECTION_ID'),
            document_id,
            {'processingStatus': 'processing'}
        )

        # Process audio and get performance data
        combined_performance, processed_files = process_recordings(
            databases, 
            storage, 
            [document_id]  # Pass as list
        )

        # Get recommendations based on filters
        queries = []
        if data.get('genreFilter', 'all') != 'all':
            queries.append(Query.equal('genre', data['genreFilter']))
        if data.get('artistFilter', 'all') != 'all':
            queries.append(Query.equal('artist', data['artistFilter']))
        
        tracks = databases.list_documents(
            os.getenv('APPWRITE_DB_ID'),
            os.getenv('APPWRITE_KARAOKE_COLLECTION_ID'),
            queries=queries
        ).get('documents', [])

        recommendations = generate_recommendations(tracks, combined_performance)

        # Prepare performance data in the exact required format
        performance_data = {
            "strongNotes": dict(sorted(combined_performance.items(), key=lambda x: x[1], reverse=True)[:5]),
            "weakNotes": dict(sorted(combined_performance.items(), key=lambda x: x[1])[:5]),
            "overallAccuracy": float(np.mean(list(combined_performance.values())))
        }

        # Prepare recommendations as a single JSON string in an array
        recommendation_data = [{
            'id': r['id'],
            'songName': r['songName'],
            'artist': r['artist'],
            'similarity': r['similarity'],
            'genre': r['genre']
        } for r in recommendations]

        # Prepare the complete result object
        result = {
            'processingStatus': 'completed',
            'recommendations': [json.dumps(recommendation_data)],  # Single JSON string in array
            'performanceData': [json.dumps(performance_data)],  # Single JSON string in array
            'crepeAnalysis': json.dumps({
                'totalNotes': len(combined_performance),
                'noteDistribution': performance_data['strongNotes'],
                'frequencyRange': {
                    'lowest': min(combined_performance.items(), key=lambda x: x[1]),
                    'highest': max(combined_performance.items(), key=lambda x: x[1])
                }
            }),
            'processedAt': datetime.datetime.now().isoformat(),
            'accuracyScore': int(performance_data['overallAccuracy'] * 100),
            'genreFilter': data.get('genreFilter', 'all'),
            'artistFilter': data.get('artistFilter', 'all'),
            'fileIds': file_ids,
            'fileId': file_ids[0] if file_ids else '',
            'isMasterDocument': data.get('isMasterDocument', False),
            'childDocuments': data.get('childDocuments', [])
        }

        # Update document with results
        databases.update_document(
            os.getenv('APPWRITE_DB_ID'),
            os.getenv('APPWRITE_USER_TRACKS_COLLECTION_ID'),
            document_id,
            result
        )
        
        print(f"✅ Updated document {document_id}", flush=True)


    except Exception as e:
        print(f"Processing failed: {str(e)}")
        # Update document with error
        databases.update_document(
            os.getenv('APPWRITE_DB_ID'),
            os.getenv('APPWRITE_USER_TRACKS_COLLECTION_ID'),
            document_id,
            {
                'processingStatus': 'failed',
                'error': str(e)[:250],  # Truncate long errors
                'failedAt': datetime.datetime.now().isoformat()
            }
        )
        raise
        
if __name__ == "__main__":
    print("Testing note frequency generation...")
    notes = generate_note_frequencies()
    print(f"Generated {len(notes)} notes")
    print("First octave:", {k:v for k,v in notes.items() if k.endswith('0')})
    print("Middle C (C4):", notes.get('C4', 'Not found'))
