import os
import tempfile
import zipfile
from flask import Flask, request, render_template, send_from_directory, jsonify, session
from werkzeug.utils import secure_filename
from moviepy.editor import AudioFileClip

# 用於中文簡繁轉換
import opencc
# xinference 所需
from xinference.client import Client

# 初始化簡體→繁體轉換器
converter = opencc.OpenCC('s2t')

# 建立 XInference 客戶端 & 模型 (請確認 host/port 正確)
client = Client("http://localhost:9997")
# model = client.get_model("SenseVoiceSmall")
model = client.get_model("whisper-large-v3-turbo")

# 允許的上傳格式：mp4 或 mp3
ALLOWED_EXTENSIONS = {'mp4', 'mp3'}

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # session 需要 secret key

def allowed_file(filename):
    """檢查上傳檔案是否為允許的格式 (mp4, mp3)"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET'])
def index():
    """
    首頁：顯示表單（前端）讓使用者上傳 MP4 或 MP3，
    後端做「(MP4→MP3) → 語音辨識 → TXT → ZIP」。
    """
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    """接收 MP4/MP3, 若是 MP4 先轉為 MP3，再做語音辨識並輸出TXT，最後打包ZIP"""
    if 'videos' not in request.files:
        return jsonify({'error': '沒有檔案被上傳'}), 400

    files = request.files.getlist('videos')
    if not files:
        return jsonify({'error': '請選擇至少一個 MP4 或 MP3 檔案'}), 400

    # 建立臨時資料夾
    temp_dir = tempfile.mkdtemp()
    audio_files_info = []

    for file in files:
        if file.filename == '':
            continue
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            upload_filepath = os.path.join(temp_dir, original_filename)
            file.save(upload_filepath)

            try:
                base, ext = os.path.splitext(original_filename)
                ext_lower = ext.lower()

                # 若為 MP4，先轉成 MP3
                if ext_lower == '.mp4':
                    # 轉 MP3
                    mp3_filename = base + '.mp3'
                    mp3_filepath = os.path.join(temp_dir, mp3_filename)

                    audioclip = AudioFileClip(upload_filepath)
                    audioclip.write_audiofile(mp3_filepath)
                    audioclip.close()

                    # 刪除原先 mp4 檔
                    os.remove(upload_filepath)
                
                else:
                    # 若原本就是 MP3，直接使用
                    mp3_filename = original_filename
                    mp3_filepath = upload_filepath  # 不需重新命名

                # 執行語音辨識
                with open(mp3_filepath, 'rb') as f:
                    audio_bytes = f.read()
                transcription = model.transcriptions(audio_bytes)
                text = transcription.get('text', '')

                # 簡體 → 繁體
                text = converter.convert(text)

                # 寫入 TXT
                txt_filename = os.path.splitext(mp3_filename)[0] + '.txt'
                txt_filepath = os.path.join(temp_dir, txt_filename)
                with open(txt_filepath, "w", encoding="utf-8") as txt_file:
                    txt_file.write(text)

                audio_files_info.append({
                    'original_filename': original_filename,
                    'mp3_filename': mp3_filename,
                    'mp3_filepath': mp3_filepath,
                    'txt_filename': txt_filename,
                    'txt_filepath': txt_filepath,
                    'transcription': text
                })

            except Exception as e:
                return jsonify({'error': f'處理 {original_filename} 時發生錯誤: {str(e)}'}), 500

    if audio_files_info:
        # 打包 MP3 + TXT 到 ZIP
        zip_filename = 'converted_audio_files.zip'
        zip_filepath = os.path.join(temp_dir, zip_filename)
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for audio_info in audio_files_info:
                # 加入 MP3
                zipf.write(audio_info['mp3_filepath'], audio_info['mp3_filename'])
                # 加入 TXT
                zipf.write(audio_info['txt_filepath'], audio_info['txt_filename'])

        # 儲存 ZIP 路徑、以便後續下載
        session['zip_download_url'] = zip_filename
        session['zip_filepath'] = zip_filepath

        return jsonify({
            'success': True,
            'download_ready': True,
            'audio_files_info': [
                {
                    'original_filename': info['original_filename'],
                    'mp3_filename': info['mp3_filename'],
                    'txt_filename': info['txt_filename'],
                    'transcription': info['transcription']
                }
                for info in audio_files_info
            ],
            'message': '轉換及語音辨識完成！已產生 MP3 和 TXT，請點擊下載按鈕下載 ZIP。'
        })
    else:
        return jsonify({'error': '沒有可處理的檔案或檔案格式不支援'}), 400

@app.route('/download_zip')
def download_zip():
    """提供已轉換 MP3/TXT ZIP 檔案下載"""
    zip_filename = session.get('zip_download_url')
    zip_filepath = session.get('zip_filepath')

    if zip_filename and zip_filepath and os.path.exists(zip_filepath):
        return send_from_directory(os.path.dirname(zip_filepath), zip_filename, as_attachment=True)
    else:
        return "沒有可下載的檔案，請先上傳並轉換", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
