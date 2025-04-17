import sys
import serial
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel,
                             QVBoxLayout, QHBoxLayout, QWidget, QProgressBar,
                             QGridLayout, QFrame, QSlider)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QColor, QPalette




#   이게 이쁜거 (나중에 프로그레스 바 등등 뜯어낼거 많음/ 그리고 소리 추가할거면 이게 나음)
class SerialThread(QThread):
    received = pyqtSignal(str)

    def __init__(self, port, baudrate):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True

    def run(self):
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=0.1)
            while self.running:
                if self.serial.in_waiting > 0:
                    data = self.serial.readline().decode('utf-8').strip()
                    if data:
                        self.received.emit(data)
                time.sleep(0.01)
        except Exception as e:
            print(f"시리얼 통신 오류: {e}")

    def send_command(self, command):
        if hasattr(self, 'serial') and self.serial.is_open:
            self.serial.write(f"{command}\n".encode('utf-8'))

    def stop(self):
        self.running = False
        if hasattr(self, 'serial') and self.serial.is_open:
            self.serial.close()


class SegmentDisplay(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(200, 80)
        self.value = "0000"

    def set_value(self, value):
        self.value = value.zfill(4)[:4]  # 항상 4자리 표시
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        from PyQt5.QtGui import QPainter, QPen, QBrush

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width() / 4

        # 각 자릿수를 그림
        for i, digit in enumerate(self.value):
            x = i * width
            y = 0
            self.draw_digit(painter, x, y, width, int(digit))

    def draw_digit(self, painter, x, y, width, digit):
        from PyQt5.QtGui import QPen, QBrush
        from PyQt5.QtCore import QRect, QPoint, QLine

        # 세그먼트 색상
        on_color = QColor(255, 0, 0)  # 켜진 상태
        off_color = QColor(50, 50, 50)  # 꺼진 상태

        # 7-세그먼트 표시 패턴 (a, b, c, d, e, f, g)
        segments = {
            0: (True, True, True, True, True, True, False),
            1: (False, True, True, False, False, False, False),
            2: (True, True, False, True, True, False, True),
            3: (True, True, True, True, False, False, True),
            4: (False, True, True, False, False, True, True),
            5: (True, False, True, True, False, True, True),
            6: (True, False, True, True, True, True, True),
            7: (True, True, True, False, False, False, False),
            8: (True, True, True, True, True, True, True),
            9: (True, True, True, True, False, True, True)
        }

        # 세그먼트 위치 계산
        height = width * 2
        segment_width = width * 0.8
        segment_height = width * 0.15

        # 각 세그먼트 그리기
        painter.setPen(QPen(Qt.black, 1))

        segment_positions = [
            (x + width / 2, y + segment_height / 2, segment_width, segment_height, 0),  # a
            (x + width - segment_height / 2, y + height / 4, segment_height, segment_width / 2, 90),  # b
            (x + width - segment_height / 2, y + height * 3 / 4, segment_height, segment_width / 2, 90),  # c
            (x + width / 2, y + height - segment_height / 2, segment_width, segment_height, 0),  # d
            (x + segment_height / 2, y + height * 3 / 4, segment_height, segment_width / 2, 90),  # e
            (x + segment_height / 2, y + height / 4, segment_height, segment_width / 2, 90),  # f
            (x + width / 2, y + height / 2, segment_width, segment_height, 0)  # g
        ]

        for i, (segment_x, segment_y, seg_width, seg_height, angle) in enumerate(segment_positions):
            is_on = segments[digit][i]
            color = on_color if is_on else off_color

            painter.save()
            painter.translate(segment_x, segment_y)
            if angle:
                painter.rotate(angle)
            painter.translate(-seg_width / 2, -seg_height / 2)

            painter.setBrush(QBrush(color))
            painter.drawRect(0, 0, seg_width, seg_height)
            painter.restore()


class RGBLed(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(60, 60)
        self.r = 0
        self.g = 0
        self.b = 0

    def set_color(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        from PyQt5.QtGui import QPainter, QPen, QBrush

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # LED 색상 설정
        color = QColor(self.r, self.g, self.b)

        # 테두리와 원 그리기
        painter.setPen(QPen(Qt.black, 2))
        painter.setBrush(QBrush(color))
        painter.drawEllipse(5, 5, 50, 50)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_serial()

    def init_serial(self):
        self.serial_thread = SerialThread('COM13', 115200)
        self.serial_thread.received.connect(self.handle_received_data)
        self.serial_thread.start()

    def init_ui(self):
        self.setWindowTitle('STM32 보드 제어')
        self.setGeometry(100, 100, 800, 600)

        # 메인 위젯과 레이아웃
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # 상단 LED 영역
        led_layout = QHBoxLayout()
        self.leds = []
        for i in range(4):
            led = QFrame()
            led.setFixedSize(50, 50)
            led.setStyleSheet("background-color: gray; border-radius: 25px;")
            led.is_on = False
            self.leds.append(led)
            led_layout.addWidget(led)
        main_layout.addLayout(led_layout)

        # RGB LED
        rgb_layout = QHBoxLayout()
        rgb_label = QLabel("RGB LED:")
        rgb_layout.addWidget(rgb_label)

        self.rgb_led = RGBLed()
        rgb_layout.addWidget(self.rgb_led)

        # RGB 슬라이더
        rgb_sliders_layout = QGridLayout()
        self.r_slider = QSlider(Qt.Horizontal)
        self.g_slider = QSlider(Qt.Horizontal)
        self.b_slider = QSlider(Qt.Horizontal)

        self.r_slider.setRange(0, 255)
        self.g_slider.setRange(0, 255)
        self.b_slider.setRange(0, 255)

        self.r_slider.valueChanged.connect(self.update_rgb)
        self.g_slider.valueChanged.connect(self.update_rgb)
        self.b_slider.valueChanged.connect(self.update_rgb)

        rgb_sliders_layout.addWidget(QLabel("R:"), 0, 0)
        rgb_sliders_layout.addWidget(self.r_slider, 0, 1)
        rgb_sliders_layout.addWidget(QLabel("G:"), 1, 0)
        rgb_sliders_layout.addWidget(self.g_slider, 1, 1)
        rgb_sliders_layout.addWidget(QLabel("B:"), 2, 0)
        rgb_sliders_layout.addWidget(self.b_slider, 2, 1)

        rgb_layout.addLayout(rgb_sliders_layout)
        main_layout.addLayout(rgb_layout)

        # 4자리 세그먼트 디스플레이
        segment_layout = QHBoxLayout()
        segment_layout.addWidget(QLabel("7-Segment:"))
        self.segment_display = SegmentDisplay()
        segment_layout.addWidget(self.segment_display)

        # 세그먼트 테스트 버튼
        self.segment_test_button = QPushButton("테스트")
        self.segment_test_button.clicked.connect(self.test_segment)
        segment_layout.addWidget(self.segment_test_button)

        main_layout.addLayout(segment_layout)

        # 프로그레스 바
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("Progress:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.progress_bar)
        main_layout.addLayout(progress_layout)

        # 버튼 영역
        button_layout = QHBoxLayout()
        self.buttons = []
        for i in range(5):
            btn = QPushButton(f"SW{i + 1}")
            btn.setFixedSize(80, 50)
            btn.clicked.connect(lambda checked, idx=i: self.button_clicked(idx))
            self.buttons.append(btn)
            button_layout.addWidget(btn)
        main_layout.addLayout(button_layout)

        # 상태 표시
        self.status_label = QLabel("상태: COM13에 연결 중...")
        main_layout.addWidget(self.status_label)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 타이머 설정 (프로그레스바 테스트용)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(100)
        self.progress_value = 0

    def button_clicked(self, idx):
        print(f"버튼 {idx + 1} 클릭됨")
        # STM32로 명령 전송
        command = f"BTN{idx + 1}"
        self.serial_thread.send_command(command)

    def update_rgb(self):
        r = self.r_slider.value()
        g = self.g_slider.value()
        b = self.b_slider.value()
        self.rgb_led.set_color(r, g, b)

        # STM32로 RGB 값 전송
        command = f"RGB:{r},{g},{b}"
        self.serial_thread.send_command(command)

    def update_progress(self):
        # 테스트용 프로그레스바 업데이트
        self.progress_value = (self.progress_value + 1) % 101
        self.progress_bar.setValue(self.progress_value)

        # 실제 사용시에는 STM32에서 수신한 값으로 업데이트할 수 있음

    def test_segment(self):
        # 테스트용 랜덤 숫자 표시
        import random
        value = str(random.randint(0, 9999)).zfill(4)
        self.segment_display.set_value(value)

        # STM32로 세그먼트 값 전송
        command = f"SEG:{value}"
        self.serial_thread.send_command(command)

    def handle_received_data(self, data):
        print(f"수신된 데이터: {data}")

        try:
            # 데이터 파싱 예시: "LED:1,ON" 또는 "BTN:2,PRESS"
            parts = data.split(':')
            if len(parts) == 2:
                cmd_type = parts[0]
                cmd_data = parts[1]

                if cmd_type == "LED":
                    led_parts = cmd_data.split(',')
                    if len(led_parts) == 2:
                        led_num = int(led_parts[0])
                        led_state = led_parts[1]

                        if 0 <= led_num < 4:  # LED 번호 유효성 확인
                            if led_state == "ON":
                                self.leds[led_num].setStyleSheet("background-color: green; border-radius: 25px;")
                                self.leds[led_num].is_on = True
                            else:
                                self.leds[led_num].setStyleSheet("background-color: gray; border-radius: 25px;")
                                self.leds[led_num].is_on = False

                elif cmd_type == "RGB":
                    rgb_values = cmd_data.split(',')
                    if len(rgb_values) == 3:
                        r = int(rgb_values[0])
                        g = int(rgb_values[1])
                        b = int(rgb_values[2])

                        self.r_slider.setValue(r)
                        self.g_slider.setValue(g)
                        self.b_slider.setValue(b)
                        self.rgb_led.set_color(r, g, b)

                elif cmd_type == "SEG":
                    self.segment_display.set_value(cmd_data)

                elif cmd_type == "PROG":
                    value = int(cmd_data)
                    self.progress_bar.setValue(value)

        except Exception as e:
            print(f"데이터 처리 오류: {e}")

        self.status_label.setText(f"상태: 수신됨 - {data}")

    def closeEvent(self, event):
        # 앱 종료 시 시리얼 통신 스레드 종료
        self.serial_thread.stop()
        self.serial_thread.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())