# video2text

```bash 
pip install -r requirements.txt
```

### 開啟xinference
```
xinference-local --host 0.0.0.0 --port 9997

```
### 先開啟另外一個終端
### 開啟whisper-large-v3-turbo (gpu者)
```bash
xinference launch --model-name whisper-large-v3-turbo --model-type audio --n-gpu 1 
```


### 或者開啟whisper-large-v3-turbo (cpu者)
```bash
xinference launch --model-name whisper-large-v3-turbo --model-type audio --n-gpu none
```

### 最後開啟flask server
```bash
flask run --host 0.0.0.0 --port=5003 
```

### 然後開啟 localhost:5003 就可以使用