
import os
import sqlite3
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'}
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect('videos.db')
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_size INTEGER,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            views INTEGER DEFAULT 0,
            description TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_size(file_path):
    """Get file size in bytes"""
    return os.path.getsize(file_path)

@app.route('/')
def index():
    """Main page showing all videos"""
    conn = sqlite3.connect('videos.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT id, title, filename, upload_date, views, description, file_size
        FROM videos 
        ORDER BY upload_date DESC
    ''')
    
    videos = []
    for row in c.fetchall():
        video = {
            'id': row[0],
            'title': row[1],
            'filename': row[2],
            'upload_date': row[3],
            'views': row[4],
            'description': row[5],
            'file_size_mb': round(row[6] / (1024 * 1024), 2) if row[6] else 0
        }
        videos.append(video)
    
    conn.close()
    return render_template('video_platform.html', videos=videos)

@app.route('/upload', methods=['GET', 'POST'])
def upload_video():
    """Handle video upload"""
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['file']
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if not title:
            flash('Title is required')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Generate unique filename
            original_filename = secure_filename(file.filename)
            file_extension = original_filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            try:
                # Save the file
                file.save(file_path)
                file_size = get_file_size(file_path)
                
                # Save to database
                conn = sqlite3.connect('videos.db')
                c = conn.cursor()
                
                c.execute('''
                    INSERT INTO videos (title, filename, original_filename, file_size, description)
                    VALUES (?, ?, ?, ?, ?)
                ''', (title, unique_filename, original_filename, file_size, description))
                
                conn.commit()
                conn.close()
                
                flash('Video uploaded successfully!')
                return redirect(url_for('index'))
                
            except Exception as e:
                flash(f'Error uploading video: {str(e)}')
                if os.path.exists(file_path):
                    os.remove(file_path)
                return redirect(request.url)
        else:
            flash('Invalid file type. Please upload a video file.')
            return redirect(request.url)
    
    return render_template('upload.html')

@app.route('/watch/<int:video_id>')
def watch_video(video_id):
    """Watch a specific video"""
    conn = sqlite3.connect('videos.db')
    c = conn.cursor()
    
    # Get video details
    c.execute('''
        SELECT id, title, filename, description, upload_date, views
        FROM videos 
        WHERE id = ?
    ''', (video_id,))
    
    video = c.fetchone()
    if not video:
        flash('Video not found')
        return redirect(url_for('index'))
    
    # Increment view count
    c.execute('UPDATE videos SET views = views + 1 WHERE id = ?', (video_id,))
    conn.commit()
    
    video_data = {
        'id': video[0],
        'title': video[1],
        'filename': video[2],
        'description': video[3],
        'upload_date': video[4],
        'views': video[5] + 1
    }
    
    conn.close()
    return render_template('watch.html', video=video_data)

@app.route('/stream/<filename>')
def stream_video(filename):
    """Stream video file"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=False)
        else:
            return "Video not found", 404
    except Exception as e:
        return f"Error streaming video: {str(e)}", 500

@app.route('/delete/<int:video_id>', methods=['POST'])
def delete_video(video_id):
    """Delete a video"""
    conn = sqlite3.connect('videos.db')
    c = conn.cursor()
    
    # Get filename before deleting from database
    c.execute('SELECT filename FROM videos WHERE id = ?', (video_id,))
    result = c.fetchone()
    
    if result:
        filename = result[0]
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Delete from database
        c.execute('DELETE FROM videos WHERE id = ?', (video_id,))
        conn.commit()
        
        # Delete file from filesystem
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file: {e}")
        
        flash('Video deleted successfully!')
    else:
        flash('Video not found')
    
    conn.close()
    return redirect(url_for('index'))

@app.route('/api/videos')
def api_videos():
    """API endpoint to get all videos as JSON"""
    conn = sqlite3.connect('videos.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT id, title, filename, upload_date, views, description, file_size
        FROM videos 
        ORDER BY upload_date DESC
    ''')
    
    videos = []
    for row in c.fetchall():
        video = {
            'id': row[0],
            'title': row[1],
            'filename': row[2],
            'upload_date': row[3],
            'views': row[4],
            'description': row[5],
            'file_size': row[6]
        }
        videos.append(video)
    
    conn.close()
    return jsonify(videos)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
