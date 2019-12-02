switch (element.event) {
    case 'text_message':
        display_message(
            element.user,
            element.date_modified,
            element.data.message,
            element.data.receiver !== null);
        break;
    case 'image_message':
        display_image(
            element.user,
            element.date_modified,
            element.data.url,
            element.data.width,
            element.data.height,
            element.data.receiver !== null);
        break;
}
