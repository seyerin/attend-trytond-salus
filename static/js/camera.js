const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const context = canvas.getContext('2d');

// Muat model-model face-api.js
Promise.all([
    faceapi.nets.tinyFaceDetector.loadFromUri('/models'),
    faceapi.nets.faceLandmark68Net.loadFromUri('/models'),
    faceapi.nets.faceRecognitionNet.loadFromUri('/models')
]).then(startVideo);

function startVideo() {
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            video.srcObject = stream;
        })
        .catch(err => console.error(err));
}

document.getElementById('snap').addEventListener('click', async () => {
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const detections = await faceapi.detectAllFaces(video, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks().withFaceDescriptors();
    
    if (detections.length > 0) {
        const faceEncoding = detections[0].descriptor;

        // Kirim face encoding ke server untuk penyimpanan atau verifikasi
        fetch('/face_recognition/save_encoding', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ encoding: faceEncoding })
        }).then(response => response.json())
          .then(data => alert(data.message))
          .catch(error => console.error('Error:', error));
    } else {
        alert('No face detected.');
    }
});
