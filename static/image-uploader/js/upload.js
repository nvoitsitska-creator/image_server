document.addEventListener('DOMContentLoaded', function () {
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' || event.key === 'F5') {
            event.preventDefault();
            window.location.href = '/';
        }
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const fileUpload = document.getElementById('file-upload');
    const imagesButton = document.getElementById('images-tab-btn');
    const dropzone = document.querySelector('.upload__dropzone');
    const currentUploadInput = document.querySelector('.upload__input');
    const copyButton = document.querySelector('.upload__copy');

    const updateTabStyles = () => {
        const uploadTab = document.getElementById('upload-tab-btn');
        const imagesTab = document.getElementById('images-tab-btn');

        const isImagesPage = window.location.pathname.includes('images');

        uploadTab.classList.remove('upload__tab--active');
        imagesTab.classList.remove('upload__tab--active');

        if (isImagesPage) {
            imagesTab.classList.add('upload__tab--active');
        } else {
            uploadTab.classList.add('upload__tab--active');
        }
    };

    const uploadFileToServer = async (file) => {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                const storedFiles = JSON.parse(localStorage.getItem('uploadedImages')) || [];
                storedFiles.push({ name: result.filename, url: result.url });
                localStorage.setItem('uploadedImages', JSON.stringify(storedFiles));

                if (currentUploadInput) {
                    currentUploadInput.value = window.location.origin + result.url;
                }
                updateTabStyles();
                return true;
            } else {
                alert(result.error || 'Upload failed');
                return false;
            }
        } catch (error) {
            alert('Upload error: ' + error.message);
            return false;
        }
    };

    const handleFiles = async (files) => {
        if (!files || files.length === 0) {
            return;
        }

        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif'];
        const MAX_SIZE_MB = 5;
        const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;
        let filesUploaded = false;

        for (const file of files) {
            if (!allowedTypes.includes(file.type)) {
                alert(`File "${file.name}" has unsupported format. Only .jpg, .png and .gif are allowed.`);
                continue;
            }
            if (file.size > MAX_SIZE_BYTES) {
                alert(`File "${file.name}" is too large. Maximum size is 5MB.`);
                continue;
            }

            const success = await uploadFileToServer(file);
            if (success) {
                filesUploaded = true;
            }
        }

        if (filesUploaded) {
            alert("Files uploaded successfully! Go to the 'Images' tab to view them.");
        }
    };

    if (copyButton && currentUploadInput) {
        copyButton.addEventListener('click', () => {
            const textToCopy = currentUploadInput.value;

            if (textToCopy && textToCopy !== 'https://') {
                navigator.clipboard.writeText(textToCopy).then(() => {
                    copyButton.textContent = 'COPIED!';
                    setTimeout(() => {
                        copyButton.textContent = 'COPY';
                    }, 2000);
                }).catch(err => {
                    console.error('Failed to copy text: ', err);
                });
            }
        });
    }

    if (imagesButton) {
        imagesButton.addEventListener('click', () => {
            window.location.href = '/form/images.html';
        });
    }

    fileUpload.addEventListener('change', (event) => {
        handleFiles(event.target.files);
        event.target.value = '';
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    dropzone.addEventListener('drop', (event) => {
        handleFiles(event.dataTransfer.files);
    });

    updateTabStyles();
});
