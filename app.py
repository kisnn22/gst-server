#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "esp_camera.h"

// ===== WIFI =====
#define WIFI_SSID "Nothing Phone"
#define WIFI_PASSWORD "22kishan2006"

// ===== SERVER =====
const char* host = "gst-server-sn8q.onrender.com";

// ===== PINS =====
#define FLASH 4
#define BUZZER 12
#define IR_SENSOR 13 // Connect IR Proximity Sensor OUT to GPIO 13

unsigned long lastCapture = 0;

// ===== BUZZER FUNCTION =====
void beep(int n){
  for(int i=0;i<n;i++){
    digitalWrite(BUZZER, HIGH);
    delay(100);
    digitalWrite(BUZZER, LOW);
    delay(100);
  }
}

// ===== SEND IMAGE =====
String sendImage(){

  // A mobile phone screen is essentially a glowing lightbulb. 
  // We MUST give the camera's Auto-Exposure (AE) algorithm time to adjust its gain,
  // otherwise it will be completely washed out and blurry bright white.
  // We do this by capturing and immediately throwing away 6 frames over ~1.2 seconds.
  for (int i = 0; i < 6; i++) {
    camera_fb_t *dummy_fb = esp_camera_fb_get();
    if (dummy_fb) {
      esp_camera_fb_return(dummy_fb);
    }
    delay(200); // 200ms between dummy captures gives the sensor more time to adjust
  }

  // NOW capture the actual, well-exposed frame
  camera_fb_t *fb = esp_camera_fb_get();

  if(!fb){
    Serial.println("❌ Camera capture failed");
    return "";
  }

  String res = "";
  
  // Retry loop to solve "HTTP Error -3" (payload send failure) and server timeouts
  for (int retry = 0; retry < 3; retry++) {
    Serial.printf("📡 Sending image to server... (Attempt %d/3)\n", retry + 1);
    
    WiFiClientSecure client;
    client.setInsecure();
    client.setTimeout(30); // 30 seconds timeout
    client.setHandshakeTimeout(30); // Increase SSL handshake timeout

    HTTPClient http;
    http.setTimeout(30000); // 30,000 milliseconds for the HTTP payload upload
    
    String url = String("https://") + host + "/upload";
    http.begin(client, url);
    http.addHeader("Content-Type", "application/octet-stream");

    int httpResponseCode = http.POST(fb->buf, fb->len);
    
    if (httpResponseCode > 0) {
      Serial.printf("HTTP Response code: %d\n", httpResponseCode);
      res = http.getString();
      http.end();
      break; // Success or received an actual HTTP response
    } else {
      Serial.printf("❌ Error code: %d - %s\n", httpResponseCode, http.errorToString(httpResponseCode).c_str());
      http.end();
      if(retry < 2) {
          Serial.println("⚠ Retrying in 2 seconds...");
          delay(2000);
      }
    }
  }

  esp_camera_fb_return(fb);

  if(res == "") {
    return "";
  }

  // JSON extract
  if(res.indexOf("{") != -1){
    res = res.substring(res.indexOf("{"));
  } else {
    // If it's an HTML error page (e.g. 500 error), return empty string
    Serial.println("❌ Failed to parse valid JSON from server response.");
    return "";
  }

  return res;
}

// ===== CAMERA SETUP =====
void startCamera(){
  camera_config_t config;

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = 5;
  config.pin_d1 = 18;
  config.pin_d2 = 19;
  config.pin_d3 = 21;
  config.pin_d4 = 36;
  config.pin_d5 = 39;
  config.pin_d6 = 34;
  config.pin_d7 = 35;
  config.pin_xclk = 0;
  config.pin_pclk = 22;
  config.pin_vsync = 25;
  config.pin_href = 23;
  config.pin_sscb_sda = 26;
  config.pin_sscb_scl = 27;
  config.pin_pwdn = 32;
  config.pin_reset = -1;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size = FRAMESIZE_XGA; // 1024x768 significantly improves OCR quality while avoiding huge memory usage
    config.jpeg_quality = 10;          // Higher quality for text
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_SVGA; 
    config.jpeg_quality = 12; 
    config.fb_count = 1;
  }

  esp_camera_init(&config);
  
  // Adjust sensor settings for better image quality & text scanning
  sensor_t * s = esp_camera_sensor_get();
  if (s != NULL) {
    s->set_lenc(s, 1);         // Enable lens correction
    s->set_dcw(s, 1);          // Enable downsize en
    s->set_sharpness(s, 2);    // Max sharpness to reduce blur on text
    s->set_contrast(s, 2);     // Max contrast for better text reading
    s->set_brightness(s, 0);   // Keep brightness normal
    s->set_saturation(s, -2);  // Lower saturation to make it black&white-ish and reduce color noise
    
    // Crucial settings for pointing camera at a lighted phone screen:
    s->set_exposure_ctrl(s, 1); // Enable auto exposure
    s->set_aec2(s, 1);          // Enable advanced auto exposure
    s->set_ae_level(s, -1);     // Force exposure slightly lower (darker) - tested optimal for phone screens
    s->set_gain_ctrl(s, 1);     // Enable auto gain
    s->set_gainceiling(s, (gainceiling_t)0); // Keep gain low to reduce grain/noise
  }
}

// ===== SETUP =====
void setup(){
  Serial.begin(115200);

  pinMode(FLASH, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  pinMode(IR_SENSOR, INPUT_PULLUP); // Setup IR sensor pin

  Serial.println("🔌 Connecting WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while(WiFi.status() != WL_CONNECTED){
    delay(500);
    Serial.print(".");
  }

  Serial.println("\n✅ WiFi Connected");

  startCamera();

  Serial.println("🚀 SYSTEM READY");
}

// ===== LOOP =====
void loop(){

  Serial.println("😴 Rest Mode - Waiting for invoice...");
  
  // Stay in this loop while no object is detected by the IR sensor (HIGH means nothing detected)
  while(digitalRead(IR_SENSOR) == HIGH) {
    delay(100);
  }

  // Once an object is placed in front, IR_SENSOR goes LOW
  Serial.println("\n🔥 Object Detected!");
  Serial.println("👀 Capturing high-quality image to check if it's an invoice bill...");
  
  // Short beep to acknowledge object detection
  digitalWrite(BUZZER, HIGH);
  delay(100);
  digitalWrite(BUZZER, LOW);
  
  // Wait 1.5 seconds so the user has time to stabilize the object
  delay(1500); 

  Serial.println("📡 Sending good quality image to server...");

  String res = sendImage();

  if(res == ""){
    Serial.println("❌ No response. Going to rest mode.");
    delay(3000);
    return;
  }

  // ===== CHECK VALIDITY / EARLY EXITS =====
  if(res.indexOf("NOT_INVOICE") != -1){
    Serial.println("\n❌ Output: This is NOT an invoice bill.");
    Serial.println("🛑 Stopping further steps, returning to rest mode...\n");
    beep(5);
    delay(3000);
    return; // Exits early
  }

  if(res.indexOf("BLUR") != -1){
    Serial.println("\n⚠ Output: Image is too BLURRY for the server to read!");
    Serial.println("🛑 Please adjust camera distance/firmness and try again.\n");
    beep(1);
    delay(3000);
    return; // Exits early since server can't read the text
  }

  if(res.indexOf("PYTHON_CRASH") != -1){
    Serial.println("\n🔥 Output: Python Server Crashed! (API Error)");
    Serial.println("⚠ Google Authentication failed on your Render Server. Please check your key.json and Cloud Vision API.\n");
    beep(5);
    delay(3000);
    return; // Exits early
  }

  if(res.indexOf("FIREBASE_CRASH") != -1){
    Serial.println("\n🔥 Output: Database Crash!");
    Serial.println("⚠ SUCCESS: The OCR API successfully read your invoice!");
    
    // Extract GST to prove it actually worked
    int gstIndex = res.indexOf("\"gst\":\"");
    if(gstIndex != -1){
      int gstEnd = res.indexOf("\"", gstIndex + 7);
      String discoveredGST = res.substring(gstIndex + 7, gstEnd);
      Serial.println("✅ Discovered GST: " + discoveredGST);
    }

    Serial.println("❌ ERROR: However, saving it to Firebase Realtime Database failed (401 Auth or wrong URL).");
    beep(5);
    delay(3000);
    return;
  }
  
  // ===== IF WE REACH HERE, IT IS A READABLE INVOICE =====
  Serial.println("\n✅ Output: Invoice Bill Detected! Starting detection...");
  Serial.println("📥 Server Response:");
  Serial.println(res);

  if(res.indexOf("GST_MISSING") != -1){
    Serial.println("⚠ GST Missing");
    beep(3);
  }
  else if(res.indexOf("DUPLICATE_GST") != -1){
    Serial.println("⚠ Duplicate GST");
    beep(4);
  }
  else if(res.indexOf("VALID_INVOICE") != -1){
    Serial.println("✅ VALID INVOICE -> Proceeding further!");
    beep(2);
    // Add any further hardware steps here (e.g. turning on a green LED)
  }
  else{
    Serial.println("❓ Unknown Response");
  }

  Serial.println("🔁 Processing complete.\n");

  delay(3000); // 3 seconds cooldown before it can scan the next item
}
