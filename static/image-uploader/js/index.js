document.addEventListener('DOMContentLoaded', function () {
    const allImgBlocks = document.querySelectorAll('.hero__img');
    const randomIndex = Math.floor(Math.random() * allImgBlocks.length);
    allImgBlocks[randomIndex].classList.add('is-visible');

    document.body.style.setProperty('background-color', '#151515');

    const showcaseButton = document.querySelector('.header__button-btn');
    if (showcaseButton) {
        showcaseButton.addEventListener('click', function () {
            window.location.href = '/upload';
        });
    }

    const galleryButton = document.querySelector('.header__button-btn--gallery');
    if (galleryButton) {
        galleryButton.addEventListener('click', function () {
            window.location.href = '/form/images.html';
        });
    }

    const dbGalleryButton = document.querySelector('.header__button-btn--db-gallery');
    if (dbGalleryButton) {
        dbGalleryButton.addEventListener('click', function () {
            window.location.href = '/images-list';
        });
    }
});
