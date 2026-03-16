document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('keydown', function (event) {
        if (event.key === 'F5' || event.key === 'Escape') {
            event.preventDefault();
            window.location.href = '/upload';
        }
    });
    const fileListWrapper = document.getElementById('file-list-wrapper');
    const uploadRedirectButton = document.getElementById('upload-tab-btn');

    const escapeHtml = (text) => {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };

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

            const colName = document.createElement('div');
            colName.className = 'file-col file-col-name';
            colName.textContent = 'Name';

            const colUrl = document.createElement('div');
            colUrl.className = 'file-col file-col-url';
            colUrl.textContent = 'Url';

            const colDelete = document.createElement('div');
            colDelete.className = 'file-col file-col-delete';
            colDelete.textContent = 'Delete';

            header.appendChild(colName);
            header.appendChild(colUrl);
            header.appendChild(colDelete);
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
            button.addEventListener('click', (event) => {
                const indexToDelete = parseInt(event.currentTarget.dataset.index);
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
