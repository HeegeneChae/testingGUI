import sys
import serial
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel,
                             QVBoxLayout, QHBoxLayout, QWidget, QProgressBar,
                             QGridLayout, QFrame)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QColor, QPalette, QFont


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


class SegmentDigit(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 100)
        self.digit = 8  # 기본값 8로 설정
        self.setStyleSheet("background-color: black;")

    def set_digit(self, digit):
        self.digit = digit
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        from PyQt5.QtGui import QPainter, QPen, QBrush

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 세그먼트 색상
        on_color = QColor(255, 0, 0)  # 빨간색 (켜진 상태)
        off_color = QColor(50, 50, 50)  # 어두운 회색 (꺼진 상태)

        width = self.width()
        height = self.height()

        # 세그먼트 두께
        segment_thickness = height / 10

        # 세그먼트 패턴 (a, b, c, d, e, f, g)
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

        # 현재 숫자에 대한 세그먼트 상태 가져오기
        try:
            digit_segments = segments.get(int(self.digit), segments[8])
        except:
            digit_segments = segments[8]  # 유효하지 않은 입력은 8로 표시

        # 세그먼트 위치 계산
        segment_length = width * 0.7
        margin = (width - segment_length) / 2

        # 세그먼트 그리기
        painter.setPen(Qt.NoPen)

        # a (상단 가로)
        color = on_color if digit_segments[0] else off_color
        painter.setBrush(QBrush(color))
        painter.drawRect(margin, margin, segment_length, segment_thickness)

        # b (우측 상단 세로)
        color = on_color if digit_segments[1] else off_color
        painter.setBrush(QBrush(color))
        painter.drawRect(margin + segment_length - segment_thickness, margin,
                         segment_thickness, segment_length)

        # c (우측 하단 세로)
        color = on_color if digit_segments[2] else off_color
        painter.setBrush(QBrush(color))
        painter.drawRect(margin + segment_length - segment_thickness, margin + segment_length,
                         segment_thickness, segment_length)

        # d (하단 가로)
        color = on_color if digit_segments[3] else off_color
        painter.setBrush(QBrush(color))
        painter.drawRect(margin, margin + segment_length * 2 - segment_thickness,
                         segment_length, segment_thickness)

        # e (좌측 하단 세로)
        color = on_color if digit_segments[4] else off_color
        painter.setBrush(QBrush(color))
        painter.drawRect(margin, margin + segment_length,
                         segment_thickness, segment_length)

        # f (좌측 상단 세로)
        color = on_color if digit_segments[5] else off_color
        painter.setBrush(QBrush(color))
        painter.drawRect(margin, margin,
                         segment_thickness, segment_length)

        # g (중앙 가로)
        color = on_color if digit_segments[6] else off_color
        painter.setBrush(QBrush(color))
        painter.drawRect(margin, margin + segment_length - segment_thickness / 2,
                         segment_length, segment_thickness)


class SegmentDisplay(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setSpacing(5)

        # 4개의 7-세그먼트 숫자 생성
        self.digits = []
        for _ in range(4):
            digit = SegmentDigit(self)
            self.digits.append(digit)
            layout.addWidget(digit)

        self.setLayout(layout)
        self.setFrameShape(QFrame.Box)
        self.setStyleSheet("background-color: black; border: 2px solid gray;")

    def set_value(self, value):
        # 4자리 문자열로 변환 (빈 자리는 0으로 채움)
        value_str = str(value).zfill(4)[:4]

        # 각 자리 설정
        for i, digit in enumerate(self.digits):
            try:
                digit.set_digit(int(value_str[i]))
            except:
                digit.set_digit(8)  # 오류 시 8로 표시


class RGBLed(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(80, 80)
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
        painter.drawEllipse(5, 5, 70, 70)


class ADCBarGraph(QWidget):
    def __init__(self):
        super().__init__()
        self.value = 0
        self.setMinimumSize(300, 40)

    def set_value(self, value):
        self.value = max(0, min(100, value))  # 0-100 범위로 제한
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        from PyQt5.QtGui import QPainter, QPen, QBrush, QLinearGradient

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 테두리 그리기
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

        # 값이 0이면 그리지 않음
        if self.value == 0:
            return

        # 그라데이션 생성
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0, QColor(0, 255, 0))
        gradient.setColorAt(0.5, QColor(255, 255, 0))
        gradient.setColorAt(1, QColor(255, 0, 0))

        # 막대 그리기
        bar_width = int((self.width() - 4) * self.value / 100)
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRect(2, 2, bar_width, self.height() - 4)

        # 값 표시
        painter.setPen(QPen(Qt.black))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        text = f"{self.value}%"
        painter.drawText(self.width() / 2 - 15, self.height() / 2 + 5, text)


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
        led_label = QLabel("상태 LED:")
        led_label.setFont(QFont("Arial", 12))
        led_layout.addWidget(led_label)

        self.leds = []
        for i in range(4):
            led = QFrame()
            led.setFixedSize(50, 50)
            led.setStyleSheet("background-color: gray; border-radius: 25px; border: 2px solid black;")
            led.is_on = False
            self.leds.append(led)
            led_layout.addWidget(led)

        led_layout.addStretch()
        main_layout.addLayout(led_layout)

        # RGB LED
        rgb_layout = QHBoxLayout()
        rgb_label = QLabel("RGB LED:")
        rgb_label.setFont(QFont("Arial", 12))
        rgb_layout.addWidget(rgb_label)

        self.rgb_led = RGBLed()
        rgb_layout.addWidget(self.rgb_led)
        rgb_layout.addStretch()
        main_layout.addLayout(rgb_layout)

        # ADC 막대 그래프
        adc_layout = QHBoxLayout()
        adc_label = QLabel("ADC 값:")
        adc_label.setFont(QFont("Arial", 12))
        adc_layout.addWidget(adc_label)

        self.adc_bar = ADCBarGraph()
        adc_layout.addWidget(self.adc_bar)
        main_layout.addLayout(adc_layout)

        # 4자리 세그먼트 디스플레이
        segment_layout = QHBoxLayout()
        segment_label = QLabel("7-Segment:")
        segment_label.setFont(QFont("Arial", 12))
        segment_layout.addWidget(segment_label)


        self.segment_display = SegmentDisplay()
        segment_layout.addWidget(self.segment_display)
        segment_layout.addStretch()
        main_layout.addLayout(segment_layout)

        # 버튼 영역
        button_layout = QGridLayout()
        button_label = QLabel("제어 버튼:")
        button_label.setFont(QFont("Arial", 12))
        button_layout.addWidget(button_label, 0, 0, 1, 2)

        self.buttons = []
        for i in range(5):
            btn = QPushButton(f"SW{i + 1}")
            btn.setFixedSize(100, 60)
            btn.setFont(QFont("Arial", 12, QFont.Bold))
            btn.clicked.connect(lambda checked, idx=i: self.button_clicked(idx))
            self.buttons.append(btn)
            button_layout.addWidget(btn, (i + 1) // 3 + 1, (i + 1) % 3)

        main_layout.addLayout(button_layout)

        # 상태 표시
        self.status_label = QLabel("상태: COM13에 연결 중...")
        self.status_label.setFont(QFont("Arial", 10))
        main_layout.addWidget(self.status_label)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 초기 상태 설정
        self.segment_display.set_value("9999")  # 초기 표시 8888

    def button_clicked(self, idx):
        print(f"버튼 {idx + 1} 클릭됨")
        # STM32로 명령 전송
        command = f"BTN{idx + 1}"
        self.serial_thread.send_command(command)

    def handle_received_data(self, data):
        print(f"수신된 데이터: {data}")

        try:
            # 데이터 파싱 예시: "LED:1,ON" 또는 "ADC:75"
            parts = data.split(':')
            if len(parts) == 2:
                cmd_type = parts[0]
                cmd_data = parts[1]

                if cmd_type == "LED":
                    led_parts = cmd_data.split(',')
                    if len(led_parts) == 2:
                        led_num = int(led_parts[0])-1
                        led_state = led_parts[1].strip()

                        if 1 <= led_num <= 4:  # LED 번호 유효성 확인
                            if led_state == "ON":
                                self.leds[led_num].setStyleSheet(
                                    "background-color: green; border-radius: 25px; border: 2px solid black;")
                                self.leds[led_num].is_on = True
                            else:
                                self.leds[led_num].setStyleSheet(
                                    "background-color: gray; border-radius: 25px; border: 2px solid black;")
                                self.leds[led_num].is_on = False
                # 이거 밑에랑 합쳤음
                elif cmd_type == "RGB":
                    rgb_values = cmd_data.split(',')
                    if len(rgb_values) == 3:
                        r = int(rgb_values[0])
                        g = int(rgb_values[1])
                        b = int(rgb_values[2])
                        self.rgb_led.set_color(r, g, b)

                elif cmd_type == "SEG":
                    self.segment_display.set_value(cmd_data)

                elif cmd_type == "ADC":
                    try:
                        value = int(cmd_data)
                        self.adc_bar.set_value(value)

                        # alertLED 함수의 동작을 시뮬레이션
                        if value == 0:
                            self.rgb_led.set_color(255, 0, 0)  # 빨간색 점멸
                        elif value <= 20:
                            self.rgb_led.set_color(255, 50, 0)  # 빨간색
                        elif value <= 40:
                            self.rgb_led.set_color(255, 100, 0)  # 주황색
                        elif value <= 60:
                            self.rgb_led.set_color(0, 255, 0)  # 녹색
                        elif value <= 80:
                            self.rgb_led.set_color(0, 255, 100)  # 청녹색
                        elif value <= 95:
                            self.rgb_led.set_color(0, 50, 255)  # 파란색
                        else:
                            self.rgb_led.set_color(0, 0, 255)  # 파란색 점멸
                    except ValueError:
                        print(f"유효하지 않은 ADC 값: {cmd_data}")

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