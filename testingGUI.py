import serial
import time
import sys
import re
import threading
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QTextEdit, QCheckBox,
                               QProgressBar, QFrame)
from PySide6.QtCore import Signal, QObject, Qt

#이거는 기존 시스템처럼 해둔거

class SevenSegmentDisplay(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 50)
        self.setStyleSheet("background-color: whitesmoke;")
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)

        # 디스플레이 텍스트
        self.display_label = QLabel("12:34:56")
        self.display_label.setStyleSheet("font-family: 'Courier'; font-size: 30px; color: dimgrey;")
        self.display_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.display_label)

    def update_display(self, text):
        self.display_label.setText(text)


class SerialWorker(QObject):
    data_received = Signal(str, str, int)  # time, message, adc_value
    led_status_changed = Signal(int, bool)  # LED 인덱스, 상태

    def __init__(self, port="COM13", baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True
        self.ser = None
        self.command_queue = []
        self.lock = threading.Lock()

        # 추가: LED 상태 추적
        self.led_status = [False, False, False, False]  # 4개 LED 상태

    def open_serial(self):
        """시리얼 포트 열기"""
        if self.ser is None or not self.ser.is_open:
            try:
                self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
                print(f"시리얼 포트 {self.port} 연결됨.")
                return True
            except serial.SerialException as e:
                print(f"시리얼 포트 접근 불가: {e}")
                self.ser = None
                return False

    def close_serial(self):
        """시리얼 포트 닫기"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("시리얼 포트 닫힘")
            self.ser = None

    def stop(self):
        """작업자 스레드 중지"""
        self.running = False
        self.close_serial()

    def run(self):
        if not self.open_serial():
            print(f"시리얼 포트 {self.port}를 열 수 없습니다.")
            return

        try:
            print(f"시리얼 포트 오픈: {self.port}")
            while self.running:
                # 현재 시간 전송
                current_time = datetime.now().strftime("T%H:%M")
                if self.ser and self.ser.is_open:
                    self.ser.write(current_time.encode())
                    print(f"[현재시각: {current_time[1:]}] 전송됨")

                # 명령 대기열 처리
                with self.lock:
                    if self.command_queue:
                        command = self.command_queue.pop(0)
                        print(f"명령 전송: {command}")
                        if self.ser and self.ser.is_open:
                            self.ser.write(str(command).encode())

                # 데이터 수신
                if self.ser and self.ser.is_open:
                    data = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if data:
                        print(f"[수신 데이터] {data}")

                        # 데이터 처리 로직 강화
                        adc_value = 0
                        message = data

                        # ADC 값 파싱 - 개선된 정규식 패턴
                        adc_match = re.search(r"ADC\s*:?\s*(\d+)", data)
                        if adc_match:
                            try:
                                adc_value = int(adc_match.group(1))
                                print(f"ADC Value: {adc_value}")
                            except ValueError:
                                adc_value = 0

                        # LED 상태 파싱
                        led_match = re.search(r"LED(\d+):(ON|OFF)", data)
                        if led_match:
                            try:
                                led_index = int(led_match.group(1)) - 1  # 0-based 인덱스로 변환
                                led_status = led_match.group(2) == "ON"
                                if 0 <= led_index < 4:  # 유효한 인덱스 확인
                                    self.led_status[led_index] = led_status
                                    self.led_status_changed.emit(led_index, led_status)
                            except (ValueError, IndexError):
                                pass

                        # UI 업데이트 신호 발생
                        self.data_received.emit(current_time[1:], message, adc_value)

                time.sleep(1)

        except serial.SerialException as e:
            print(f"시리얼 오류 발생: {e}")
        finally:
            self.close_serial()

    def send_command(self, command):
        """명령어 전송"""
        if not self.ser or not self.ser.is_open:
            if not self.open_serial():
                print("시리얼 포트가 닫혀있어 명령을 전송할 수 없습니다.")
                return

        with self.lock:
            self.command_queue.append(command)
            print(f"명령 대기열 추가: {command}")

        # 즉시 전송 시도
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(str(command).encode())
                print(f"\n<실제로 STM32로 보낸 명령어: {command}>\n")
            except serial.SerialException as e:
                print(f"명령 전송 중 오류 발생: {e}")

    def toggle_led(self, index):
        """LED 토글"""
        self.led_status[index] = not self.led_status[index]
        status = "ON" if self.led_status[index] else "OFF"
        self.send_command(f"LED{index + 1}:{status}")

    def send_adc(self):
        self.send_command('R00001')

    def send_timer(self):
        self.send_command('R00002')

    def send_buzzer(self):
        self.send_command('R00003')

    def send_reset(self):
        self.send_command('R00004')

    def send_time(self):
        self.send_command('R00005')


class TraceBoard(QWidget):
    def __init__(self, serial_worker):
        super().__init__()
        self.setWindowTitle("Serial Communication Panel")
        self.serial_worker = serial_worker

        # 메인 레이아웃
        main_layout = QHBoxLayout()

        # 왼쪽 프레임 (LED 버튼)
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setAlignment(Qt.AlignTop)

        # LED 버튼 생성
        self.led_buttons = []
        for i in range(4):
            btn = QPushButton(f"LED {i + 1}")
            btn.setCheckable(True)
            btn.setMinimumWidth(100)
            btn.setStyleSheet("background-color: red;")
            btn.clicked.connect(lambda checked, idx=i: self.on_led_clicked(idx))
            left_layout.addWidget(btn)
            self.led_buttons.append(btn)

        main_layout.addWidget(left_frame)

        # 중앙 프레임
        center_frame = QFrame()
        center_layout = QVBoxLayout(center_frame)

        # 7-세그먼트 디스플레이
        self.seven_segment = SevenSegmentDisplay()
        center_layout.addWidget(self.seven_segment)

        # 로그 텍스트 영역
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMinimumHeight(150)
        center_layout.addWidget(self.text_edit)

        # 데이터 표시 라벨
        data_frame = QFrame()
        data_layout = QHBoxLayout(data_frame)

        # 왼쪽 데이터 레이블
        labels_frame = QFrame()
        labels_layout = QVBoxLayout(labels_frame)
        self.timer_label = QLabel("타이머: 00:00")
        self.time_label = QLabel("시간: 00:00")
        self.adc_label = QLabel("ADC 값: 0")

        labels_layout.addWidget(self.timer_label)
        labels_layout.addWidget(self.time_label)
        labels_layout.addWidget(self.adc_label)
        data_layout.addWidget(labels_frame)

        # ADC 프로그레스 바 (세로)
        progress_frame = QFrame()
        progress_layout = QHBoxLayout(progress_frame)

        self.adc_progress = QProgressBar()
        self.adc_progress.setOrientation(Qt.Vertical)
        self.adc_progress.setMaximum(4095)  # ADC 일반적 최대값
        self.adc_progress.setTextVisible(False)
        progress_layout.addWidget(self.adc_progress)

        # 프로그레스 레이블
        progress_labels = QFrame()
        progress_labels_layout = QVBoxLayout(progress_labels)
        progress_labels_layout.setAlignment(Qt.AlignCenter)

        progress_labels_layout.addWidget(QLabel("100%"))
        progress_labels_layout.addStretch()
        progress_labels_layout.addWidget(QLabel("50%"))
        progress_labels_layout.addStretch()
        progress_labels_layout.addWidget(QLabel("0%"))

        progress_layout.addWidget(progress_labels)
        data_layout.addWidget(progress_frame)

        center_layout.addWidget(data_frame)
        main_layout.addWidget(center_frame, 2)  # 중앙 부분에 더 많은 공간 할당

        # 버튼 프레임
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)

        self.adc_button = QPushButton('ADC 값 요청')
        self.adc_button.clicked.connect(self.on_adc_clicked)

        self.timer_button = QPushButton('타이머')
        self.timer_button.clicked.connect(self.on_timer_clicked)

        self.buzzer_button = QPushButton('실시간')
        self.buzzer_button.clicked.connect(self.on_buzzer_clicked)

        self.time_button = QPushButton('시간')
        self.time_button.clicked.connect(self.on_time_clicked)

        self.reset_button = QPushButton('리셋')
        self.reset_button.clicked.connect(self.on_reset_clicked)

        self.power_checkbox = QCheckBox('전원 OFF')
        self.power_checkbox.clicked.connect(self.close)

        button_layout.addWidget(self.adc_button)
        button_layout.addWidget(self.timer_button)
        button_layout.addWidget(self.buzzer_button)
        button_layout.addWidget(self.time_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.power_checkbox)

        # 메인 레이아웃에 모든 요소 추가
        main_vlayout = QVBoxLayout()
        main_vlayout.addLayout(main_layout)
        main_vlayout.addWidget(button_frame)

        self.setLayout(main_vlayout)

        # 시그널 연결
        self.serial_worker.data_received.connect(self.update_ui)
        self.serial_worker.led_status_changed.connect(self.update_led_status)

        # 초기 상태 설정
        self.reset_display()

    def on_led_clicked(self, index):
        """LED 토글"""
        self.text_edit.append(f"LED {index + 1} 토글 버튼 클릭됨")
        self.serial_worker.toggle_led(index)

    def update_led_status(self, index, status):
        """LED 상태 업데이트"""
        color = "green" if status else "red"
        self.led_buttons[index].setStyleSheet(f"background-color: {color};")

    def on_adc_clicked(self):
        self.text_edit.append("ADC 값 요청 버튼 클릭됨")
        self.serial_worker.send_adc()

    def on_timer_clicked(self):
        self.text_edit.append("타이머 제어 버튼 클릭됨")
        self.serial_worker.send_timer()

    def on_buzzer_clicked(self):
        self.text_edit.append("부저 제어 버튼 클릭됨")
        self.serial_worker.send_buzzer()

    def on_time_clicked(self):
        self.text_edit.append("시간 제어 버튼 클릭됨")
        self.serial_worker.send_time()

    def on_reset_clicked(self):
        self.text_edit.append("리셋 제어 버튼 클릭됨")
        self.serial_worker.send_reset()
        self.reset_display()

    def reset_display(self):
        """디스플레이 초기화"""
        self.seven_segment.update_display("00:00:00")
        self.adc_progress.setValue(0)
        self.adc_label.setText("ADC 값: 0")
        self.timer_label.setText("타이머: 00:00")
        self.time_label.setText("시간: 00:00")

    def update_ui(self, current_time, message, adc_value):
        """UI 업데이트"""
        # 로그 추가
        self.text_edit.append(f"[시간: {current_time}] 메시지: {message}")

        # 개별 데이터 업데이트
        self.timer_label.setText(f"타이머: {current_time}")
        self.time_label.setText(f"시간: {current_time}")

        # ADC 값 업데이트
        if adc_value > 0:
            self.adc_label.setText(f"ADC 값: {adc_value}")
            self.adc_progress.setValue(adc_value)

            # 7-세그먼트에 ADC 값 표시
            if message.startswith("ADC"):
                self.seven_segment.update_display(str(adc_value))

        # 타이머 값이 포함된 경우
        timer_match = re.search(r"TIMER:([0-9:]+)", message)
        if timer_match:
            self.seven_segment.update_display(timer_match.group(1))

        # 시간 값이 포함된 경우
        time_match = re.search(r"TIME:([0-9:]+)", message)
        if time_match:
            self.seven_segment.update_display(time_match.group(1))


def main():
    app = QApplication(sys.argv)

    # SerialWorker 인스턴스 생성
    serial_worker = SerialWorker(port="COM13")

    # TraceBoard에 serial_worker 전달
    window = TraceBoard(serial_worker)

    # 별도 스레드에서 SerialWorker 실행
    serial_thread = threading.Thread(target=serial_worker.run, daemon=True)
    serial_thread.start()

    window.show()

    try:
        app.exec()
    finally:
        serial_worker.stop()
        serial_thread.join(timeout=1)


if __name__ == '__main__':
    main()