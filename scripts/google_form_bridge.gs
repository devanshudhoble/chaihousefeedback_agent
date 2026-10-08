/**
 * Google Forms → Chai House feedback service bridge.
 * Store BACKEND_URL and WEBHOOK_TOKEN under Apps Script Project Settings → Script properties.
 * Add an installable On form submit trigger for onFormSubmit.
 */
function onFormSubmit(e) {
  const properties = PropertiesService.getScriptProperties();
  const backendUrl = properties.getProperty('BACKEND_URL');
  const webhookToken = properties.getProperty('WEBHOOK_TOKEN');
  if (!backendUrl || !webhookToken) throw new Error('Set BACKEND_URL and WEBHOOK_TOKEN in Script properties.');

  const payload = { namedValues: e.namedValues || {} };
  const photoEntry = Object.entries(payload.namedValues).find(([label, values]) =>
    /photo|image|upload/i.test(label) && values && values[0]
  );

  // Google Drive links are not public image bytes. The trigger owner reads the upload
  // from Drive and forwards a size-limited image so the backend vision step can review it.
  if (photoEntry) {
    const fileUrl = String(photoEntry[1][0]);
    const match = fileUrl.match(/[-\w]{25,}/);
    if (match) {
      const file = DriveApp.getFileById(match[0]);
      if (file.getSize() > 5 * 1024 * 1024) throw new Error('Photo exceeds the 5 MB feedback limit.');
      const blob = file.getBlob();
      const contentType = blob.getContentType().toLowerCase();
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(contentType)) {
        throw new Error('Photo must be JPG, PNG, or WebP.');
      }
      payload.image_url = file.getUrl();
      payload.image = {
        content_type: contentType,
        base64: Utilities.base64Encode(blob.getBytes())
      };
    }
  }

  const response = UrlFetchApp.fetch(backendUrl, {
    method: 'post',
    contentType: 'application/json',
    headers: { 'X-Webhook-Token': webhookToken },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
  const status = response.getResponseCode();
  if (status < 200 || status >= 300) {
    throw new Error(`Chai House feedback service returned ${status}: ${response.getContentText()}`);
  }
  console.log(response.getContentText());
}
