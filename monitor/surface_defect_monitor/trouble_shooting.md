
1. Qt::Orientation::Horizontal 이슈
  * QtDesigner에서 만든 QSlider에서 Orientation 속성을 Horizontal로 설정했을때 PyQt6에서 오인식 되는 문제.
  * Tested Python 3.10, pyqt6.7.0
```
- ui 파일을 열어 Qt::Orientation::Horizontal을 찾아 Qt::Horizontal로 변경해야 함
- Qt::Orientation::Horizontal 를 Qt::Horizontal로 변경
```