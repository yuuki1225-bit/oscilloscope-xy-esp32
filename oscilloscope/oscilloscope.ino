#include "driver/dac.h"

constexpr int MAX_P = 2000;     // 2000 → 3000
uint8_t bx[2][MAX_P], by[2][MAX_P];
volatile int cnt[2] = {0, 0};
volatile int front = 0;

// コア0: 点列をひたすら描き続ける
void renderTask(void *) {
  for (;;) {
    int f = front;
    int n = cnt[f];
    for (int i = 0; i < n; i++) {
      dac_output_voltage(DAC_CHANNEL_1, bx[f][i]);
      dac_output_voltage(DAC_CHANNEL_2, by[f][i]);
    }
    vTaskDelay(1);   // WDT対策
  }
}

void setup() {
  Serial.setRxBufferSize(8192);
  Serial.begin(921600);          // 921600 → 2000000
  dac_output_enable(DAC_CHANNEL_1);   // GPIO 25 (X軸)
  dac_output_enable(DAC_CHANNEL_2);   // GPIO 26 (Y軸)
  xTaskCreatePinnedToCore(renderTask, "render", 4096, NULL, 1, NULL, 0);
}

// コア1(loop): 受信
int n = 0, phase = 0;
uint8_t tx;

void loop() {
  int back = 1 - front;
  while (Serial.available()) {
    uint8_t b = Serial.read();
    if (b == 0xFF) {                       // フレーム終端
      if (phase == 0 && n > 0) {
        cnt[back] = n;
        front = back;                      // 切り替え
        back = 1 - front;
      }
      n = 0; phase = 0;
      continue;
    }
    if (phase == 0) { tx = b; phase = 1; }
    else {
      if (n < MAX_P) { bx[back][n] = tx; by[back][n] = b; n++; }
      phase = 0;
    }
  }
}