document.addEventListener('DOMContentLoaded', () => {
    registerKeyboardShortcuts('/upload');

    const fileListWrapper = document.getElementById('file-list-wrapper');
    const uploadRedirectButton = document.getElementById('upload-tab-btn');

    const escapeHtml = (text) => {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };

    const deleteFromServer = async (imageUrl) => {
        try {
            const response = await fetch(imageUrl, { method: 'DELETE' });
            return response.ok;
        } catch (error) {
            console.error('Failed to delete from server:', error);
            return false;
        }
    };

    const displayFiles = () => {
        const storedFiles = JSON.parse(localStorage.getItem('uploadedImages')) || [];
        fileListWrapper.textContent = '';

        if (storedFiles.length === 0) {
            const emptyMsg = document.createElement('p');
            emptyMsg.className = 'upload__promt';
            emptyMsg.style.textAlign = 'center';
            emptyMsg.style.marginTop = '50px';
            emptyMsg.textContent = 'No images uploaded yet.';
            fileListWrapper.appendChild(emptyMsg);
        } else {
            const container = document.createElement('div');
            container.className = 'file-list-container';

            const header = document.createElement('div');
            header.className = 'file-list-header';

            ['Name', 'Url', 'Delete'].forEach(label => {
                const col = document.createElement('div');
                col.className = `file-col file-col-${label.toLowerCase()}`;
                col.textContent = label;
                header.appendChild(col);
            });

            container.appendChild(header);

            const list = document.createElement('div');
            list.id = 'file-list';

            storedFiles.forEach((fileData, index) => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-list-item';

                const nameCol = document.createElement('div');
                nameCol.className = 'file-col file-col-name';

                const iconSpan = document.createElement('span');
                iconSpan.className = 'file-icon';
                const iconImg = document.createElement('img');
                iconImg.src = '/image-uploader/img/icon/Group.png';
                iconImg.alt = 'file icon';
                iconSpan.appendChild(iconImg);

                const nameSpan = document.createElement('span');
                nameSpan.className = 'file-name';
                nameSpan.textContent = fileData.name;

                nameCol.appendChild(iconSpan);
                nameCol.appendChild(nameSpan);

                const urlCol = document.createElement('div');
                urlCol.className = 'file-col file-col-url';
                const urlLink = document.createElement('a');
                urlLink.href = fileData.url;
                urlLink.target = '_blank';
                urlLink.textContent = fileData.url;
                urlCol.appendChild(urlLink);

                const deleteCol = document.createElement('div');
                deleteCol.className = 'file-col file-col-delete';
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'delete-btn';
                deleteBtn.dataset.index = index;
                deleteBtn.dataset.url = fileData.url;
                const deleteImg = document.createElement('img');
                deleteImg.src = '/image-uploader/img/icon/delete.png';
                deleteImg.alt = 'delete icon';
                deleteBtn.appendChild(deleteImg);
                deleteCol.appendChild(deleteBtn);

                fileItem.appendChild(nameCol);
                fileItem.appendChild(urlCol);
                fileItem.appendChild(deleteCol);
                list.appendChild(fileItem);
            });

            container.appendChild(list);
            fileListWrapper.appendChild(container);
            addDeleteListeners();
        }

        updateTabStyles();
    };

    const addDeleteListeners = () => {
        document.querySelectorAll('.delete-btn').forEach(button => {
            button.addEventListener('click', async (event) => {
                const btn = event.currentTarget;
                const indexToDelete = parseInt(btn.dataset.index);
                const imageUrl = btn.dataset.url;

                await deleteFromServer(imageUrl);

                let storedFiles = JSON.parse(localStorage.getItem('uploadedImages')) || [];
                storedFiles.splice(indexToDelete, 1);
                localStorage.setItem('uploadedImages', JSON.stringify(storedFiles));
                displayFiles();
            });
        });
    };

    if (uploadRedirectButton) {
        uploadRedirectButton.addEventListener('click', () => {
            window.location.href = '/upload';
        });
    }

    displayFiles();
});
