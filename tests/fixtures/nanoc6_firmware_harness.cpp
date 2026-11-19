// Only IO and time-source interfaces are doubled. The four tested bodies are
// extracted verbatim from the public firmware by test_nanoc6_firmware.py.
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <deque>
#include <optional>
#include <string>
#include <vector>

#define id(value) value
template<class... T> void log_debug(T...) {}
#define ESP_LOGD(...) log_debug(__VA_ARGS__)

uint64_t boot_ms = 0;
uint64_t millis_64() { return boot_ms; }
struct ESPTime {
  time_t timestamp;
  bool is_valid() const { return timestamp >= 1546300800; }
  static ESPTime from_epoch_utc(time_t epoch) { return {epoch}; }
  std::string strftime(const char *format) {
    char buffer[64];
    const auto *parts = std::gmtime(&timestamp);
    assert(parts != nullptr);
    assert(std::strftime(buffer, sizeof(buffer), format, parts) > 0);
    return buffer;
  }
};
struct Clock {
  time_t epoch = 0;
  ESPTime utcnow() const { return {epoch}; }
} report_clock;
struct Sensor {
  double state = NAN;
  void publish_state(double value) { state = value; }
};
std::optional<std::string> report_value();
struct TextSensor {
  std::vector<std::string> events;
  bool has_state() const { return !events.empty(); }
  void publish_state(const std::string &value) { events.push_back(value); }
  void update() {
    auto value = report_value();
    if (value) publish_state(*value);
  }
};
struct Uart {
  std::deque<uint8_t> bytes;
  size_t available() const { return bytes.size(); }
  bool read_byte(uint8_t *value) {
    if (bytes.empty()) return false;
    *value = bytes.front(); bytes.pop_front(); return true;
  }
} solesta_uart;

bool has_valid_status = false;
uint64_t last_valid_status_ms = 0;
uint32_t last_report_frame_sequence = 0, frame_sequence_value = 0;
uint32_t valid_frame_count_value = 0, rejected_record_count_value = 0;
uint32_t controller_state_count_value = 0;
Sensor temperature_1_raw, temperature_2_raw, temperature_3_raw, temperature_4_raw;
Sensor flow_raw, pump_raw, valid_frame_count, rejected_record_count;
Sensor frame_sequence, controller_state_count, controller_state_code;
TextSensor last_report, last_valid_status_line, controller_state_text;

std::optional<std::string> report_value() {
/* REPORT_LAMBDA */
}
bool data_valid() {
/* VALID_LAMBDA */
}
double data_age() {
/* AGE_LAMBDA */
}
void parser_tick() {
/* PARSER_LAMBDA */
}
void feed(const std::string &text) {
  for (unsigned char value : text) solesta_uart.bytes.push_back(value);
  parser_tick();
}
void reset() {
  has_valid_status = false; last_valid_status_ms = 0;
  last_report_frame_sequence = 0; frame_sequence_value = 0;
  valid_frame_count_value = 0; rejected_record_count_value = 0;
  controller_state_count_value = 0; last_report.events.clear();
  report_clock.epoch = 0; boot_ms = 0;
}
const std::string FRAME = "T|31|52|40|309_F|0.000000_PWM|0.757539\r\n";

int main() {
  constexpr time_t epoch = 1794916800;  // 2026-11-17 12:00:00 UTC
  reset();
  assert(!data_valid());
  assert(std::isnan(data_age()));
  last_report.update();
  assert(!last_report.has_state());
  report_clock.epoch = epoch;
  last_report.update();  // A clock, by itself, is not a device report.
  assert(!last_report.has_state());

  // Complete frame before clock sync; date its actual receipt after sync.
  report_clock.epoch = 0; boot_ms = 10000;
  feed(FRAME);
  assert(data_valid());
  assert(!last_report.has_state());
  boot_ms += 20000; report_clock.epoch = epoch + 20;
  last_report.update();
  assert(last_report.events.back() == "2026-11-17T12:00:00Z");
  assert(!data_valid());
  assert(data_age() == 20.0);
  const auto count = last_report.events.size();
  for (int index = 0; index < 100; ++index) {
    boot_ms += 5000; report_clock.epoch += 5;
    last_report.update();  // Diagnostic polling cannot make it fresh.
  }
  report_clock.epoch += 7200;  // Nor can an NTP clock correction.
  last_report.update();
  assert(last_report.events.size() == count);

  // Identical values in a new complete frame still advance last_report.
  report_clock.epoch = epoch + 8000; boot_ms += 1000;
  feed(FRAME);
  assert(last_report.events.size() == count + 1);
  assert(last_report.events.back() == "2026-11-17T14:13:20Z");
  assert(data_valid());
  assert(std::abs(pump_raw.state - 0.757539) < 0.000001);
  const auto received = last_report.events.back();
  const auto sequence = frame_sequence_value;
  report_clock.epoch += 5; boot_ms += 5000;
  feed("T|31|NaN|40|309_F|0_PWM|0\n");
  feed("T|31|52|40|309_F|0_PWM|1e1000\n");
  feed("unrelated log message\nZ|3|Run State\n");
  last_report.update();
  assert(frame_sequence_value == sequence);
  assert(last_report.events.back() == received);
  assert(controller_state_count_value == 1);
  assert(rejected_record_count_value == 2);
  boot_ms += 10001; report_clock.epoch += 10;
  assert(!data_valid());
  assert(last_report.events.back() == received);

  // A lost clock cannot publish a fake epoch or lose the latest frame time.
  report_clock.epoch = 0;
  feed(FRAME);
  assert(last_report.events.back() == received);
  boot_ms += 10000; report_clock.epoch = epoch + 8100;
  last_report.update();
  assert(last_report.events.back() == "2026-11-17T14:14:50Z");

  // A reboot has no persisted report until this boot actually gets a frame.
  reset(); report_clock.epoch = epoch;
  last_report.update();
  assert(!last_report.has_state());
  // Monotonic dating and validity must not wrap after 49.7 days.
  boot_ms = (1ULL << 32) - 1000;
  report_clock.epoch = 0; feed(FRAME);
  boot_ms += (1ULL << 32) + 2000;
  report_clock.epoch = epoch;
  last_report.update();
  assert(!data_valid());
  assert(last_report.events.back() == ESPTime::from_epoch_utc(
      epoch - static_cast<time_t>(((1ULL << 32) + 2000) / 1000)).strftime("%Y-%m-%dT%H:%M:%SZ"));
  std::puts("firmware report scenarios passed");
}
