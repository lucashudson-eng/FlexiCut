import sys
import cv2
import numpy as np
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, 
    QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QFrame,
    QSizePolicy, QLineEdit, QLabel, QMessageBox
)
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QImage, QPainter, QPen, QColor, QBrush, QPolygonF, QCursor

class CropWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.cv_image = None
        
        # 4 pontos normalizados (0.0 a 1.0)
        self.norm_points = [
            QPointF(0.0, 0.0), 
            QPointF(1.0, 0.0), 
            QPointF(1.0, 1.0), 
            QPointF(0.0, 1.0)  
        ]
        
        self.active_point_index = -1
        self.handle_radius = 8
        self.setMouseTracking(True)
        
        # Zoom e Pan
        self.scale = 1.0
        self.offset = QPointF(0, 0)
        self.is_panning = False
        self.last_mouse_pos = QPointF()

    def set_image(self, img):
        self.cv_image = img
        # Reset pontos
        self.norm_points = [
            QPointF(0.0, 0.0),
            QPointF(1.0, 0.0),
            QPointF(1.0, 1.0),
            QPointF(0.0, 1.0)
        ]
        self.fit_image()
        self.update()

    def fit_image(self):
        """Ajusta zoom e pan para a imagem caber na tela."""
        if self.cv_image is None:
            return
            
        h_img, w_img = self.cv_image.shape[:2]
        w_widget = self.width()
        h_widget = self.height()
        
        if w_widget == 0 or h_widget == 0:
            return

        scale_w = w_widget / w_img
        scale_h = h_widget / h_img
        self.scale = min(scale_w, scale_h) * 0.9 # 90% para dar margem
        
        # Centralizar
        disp_w = w_img * self.scale
        disp_h = h_img * self.scale
        x = (w_widget - disp_w) / 2
        y = (h_widget - disp_h) / 2
        self.offset = QPointF(x, y)

    def to_screen_coords(self, norm_point):
        """Converte ponto normalizado (0-1) para tela considerando zoom/pan."""
        if self.cv_image is None:
            return QPointF()
            
        h_img, w_img = self.cv_image.shape[:2]
        
        # Ponto na imagem original (pixels)
        img_x = norm_point.x() * w_img
        img_y = norm_point.y() * h_img
        
        # Aplica transformação
        screen_x = (img_x * self.scale) + self.offset.x()
        screen_y = (img_y * self.scale) + self.offset.y()
        
        return QPointF(screen_x, screen_y)

    def screen_to_norm(self, screen_pos):
        """Converte tela para normalizado (0-1)."""
        if self.cv_image is None:
            return QPointF()
            
        h_img, w_img = self.cv_image.shape[:2]
        
        # Remove transformação
        img_x = (screen_pos.x() - self.offset.x()) / self.scale
        img_y = (screen_pos.y() - self.offset.y()) / self.scale
        
        # Normaliza
        nx = img_x / w_img
        ny = img_y / h_img
        
        # Clamp
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))
        
        return QPointF(nx, ny)

    def wheelEvent(self, event):
        if self.cv_image is None:
            return

        # Zoom in/out
        zoom_factor = 1.15
        if event.angleDelta().y() < 0:
            zoom_factor = 1.0 / zoom_factor

        # Posição do mouse antes do zoom (relativo à imagem)
        mouse_pos = event.pos()
        old_pos_in_img = (mouse_pos - self.offset) / self.scale
        
        # Aplica zoom
        self.scale *= zoom_factor
        
        # Ajusta offset para manter o ponto sob o mouse fixo
        # mouse_pos = new_pos_in_img * new_scale + new_offset
        # onde new_pos_in_img == old_pos_in_img (queremos que seja o mesmo ponto da imagem)
        # new_offset = mouse_pos - (old_pos_in_img * new_scale)
        self.offset = mouse_pos - (old_pos_in_img * self.scale)
        
        self.update()

    def mousePressEvent(self, event):
        if self.cv_image is None:
            return

        # Botão Direito ou Meio para Pan (Arrastar a imagem)
        if event.button() == Qt.RightButton or event.button() == Qt.MiddleButton:
            self.is_panning = True
            self.last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return

        # Botão Esquerdo para Mover Pontos
        if event.button() == Qt.LeftButton:
            click_pos = event.pos()
            
            # Verificar colisão com handles
            min_dist = float('inf')
            closest_idx = -1
            limit_sq = (self.handle_radius * 2.5) ** 2 
            
            # Calcula posição dos handles na tela atual
            for i, p_norm in enumerate(self.norm_points):
                p_screen = self.to_screen_coords(p_norm)
                dist_sq = (p_screen.x() - click_pos.x())**2 + (p_screen.y() - click_pos.y())**2
                
                if dist_sq < limit_sq and dist_sq < min_dist:
                    min_dist = dist_sq
                    closest_idx = i
            
            if closest_idx != -1:
                self.active_point_index = closest_idx
            else:
                # Se clicou fora, talvez queira fazer pan também?
                # Por enquanto deixa só mover handles.
                pass

    def mouseMoveEvent(self, event):
        # Pan
        if self.is_panning:
            delta = event.pos() - self.last_mouse_pos
            self.offset += delta
            self.last_mouse_pos = event.pos()
            self.update()
            return

        # Mover Handle
        if self.active_point_index != -1 and self.cv_image is not None:
            norm_pos = self.screen_to_norm(event.pos())
            self.norm_points[self.active_point_index] = norm_pos
            self.update()

    def mouseReleaseEvent(self, event):
        self.active_point_index = -1
        if self.is_panning:
            self.is_panning = False
            self.setCursor(Qt.ArrowCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing) # Anti-aliasing para bolinhas e linhas
        painter.setRenderHint(QPainter.SmoothPixmapTransform) # Importante para a imagem
        
        painter.fillRect(self.rect(), QColor("#2d2d2d"))

        if self.cv_image is None:
            painter.setPen(QColor("#aaaaaa"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Carregue uma imagem")
            return

        h_img, w_img = self.cv_image.shape[:2]

        # 1. Desenhar Imagem Transformada
        # Calculamos onde ela aparece na tela
        dest_x = self.offset.x()
        dest_y = self.offset.y()
        dest_w = w_img * self.scale
        dest_h = h_img * self.scale
        target_rect = QRectF(dest_x, dest_y, dest_w, dest_h)
        
        # Só desenha se estiver visível (Otimização básica)
        if target_rect.intersects(QRectF(self.rect())):
            rgb = cv2.cvtColor(self.cv_image, cv2.COLOR_BGR2RGB)
            qt_img = QImage(rgb.data, w_img, h_img, 3 * w_img, QImage.Format_RGB888)
            painter.drawImage(target_rect, qt_img)

        # 2. Desenhar Handles e Linhas
        screen_points = [self.to_screen_coords(p) for p in self.norm_points]
        poly = QPolygonF(screen_points)
        
        pen = QPen(QColor(0, 255, 0), 2)
        painter.setPen(pen)
        painter.drawPolygon(poly)

        painter.setBrush(QBrush(QColor(0, 255, 0)))
        painter.setPen(Qt.NoPen)
        for p in screen_points:
            painter.drawEllipse(p, self.handle_radius, self.handle_radius)

class OpenCVApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Planificador de Imagens Pro")
        self.resize(1000, 700)
        self.setAcceptDrops(True)
        self.original_path = None
        
        # Styles
        self.setStyleSheet("""
            QMainWindow { background-color: #2d2d2d; color: white; }
            QPushButton { 
                background-color: #3c3c3c; color: white; border: 1px solid #555; 
                padding: 6px 12px; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: #4a4a4a; }
            QLineEdit {
                background-color: #1e1e1e; color: #ddd; border: 1px solid #555;
                padding: 4px; border-radius: 4px; 
            }
            QLabel { color: #cccccc; margin-left: 5px; font-size: 14px; }
            QFrame { background-color: #353535; border-bottom: 1px solid #444; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Top Bar ---
        bar = QFrame()
        bar.setFixedHeight(60)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(20, 10, 20, 10)
        
        # Btn Select
        self.btn_select = QPushButton("Selecionar Imagem")
        self.btn_select.clicked.connect(self.open_file_dialog)
        bar_layout.addWidget(self.btn_select)
        
        # Filename Logic (Separado)
        bar_layout.addWidget(QLabel("Salvar como:"))
        
        self.file_input_container = QWidget()
        fic_layout = QHBoxLayout(self.file_input_container)
        fic_layout.setContentsMargins(0,0,0,0)
        fic_layout.setSpacing(2)
        
        self.txt_filename = QLineEdit()
        self.txt_filename.setPlaceholderText("nome_arquivo")
        self.txt_filename.setFixedWidth(200)
        fic_layout.addWidget(self.txt_filename)
        
        self.lbl_extension = QLabel(".jpg")
        self.lbl_extension.setStyleSheet("color: #888; font-weight: bold;")
        fic_layout.addWidget(self.lbl_extension)
        
        bar_layout.addWidget(self.file_input_container)
        
        # Btn Save
        self.btn_save = QPushButton("Salvar Recorte")
        self.btn_save.setStyleSheet("background-color: #2a6f2a;") 
        self.btn_save.clicked.connect(self.save_warped_image)
        bar_layout.addWidget(self.btn_save)
        
        bar_layout.addStretch()
        layout.addWidget(bar)
        
        # Crop Widget
        self.crop_widget = CropWidget()
        layout.addWidget(self.crop_widget)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.load_image(urls[0].toLocalFile())

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir Imagem", "", "Imagens (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self.load_image(path)

    def load_image(self, path):
        self.original_path = path
        
        # Separa nome e extensão
        base = os.path.basename(path)
        name, ext = os.path.splitext(base)
        
        # Define os campos
        self.txt_filename.setText(f"{name}_edited")
        self.lbl_extension.setText(ext) # Mantém a extensão original (ex: .png)
        
        img = cv2.imread(path)
        if img is not None:
            self.crop_widget.set_image(img)

    def save_warped_image(self):
        img = self.crop_widget.cv_image
        if img is None:
            QMessageBox.warning(self, "Aviso", "Nenhuma imagem carregada!")
            return
        
        if not self.original_path:
            return

        h, w = img.shape[:2]
        pts_norm = self.crop_widget.norm_points
        src_pts = np.float32([ [p.x()*w, p.y()*h] for p in pts_norm ])

        # Cálculo de distância
        def dist(a, b):
            return np.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)

        width_top = dist(src_pts[0], src_pts[1])
        width_bot = dist(src_pts[3], src_pts[2])
        max_width = int(max(width_top, width_bot))

        height_left = dist(src_pts[0], src_pts[3])
        height_right = dist(src_pts[1], src_pts[2])
        max_height = int(max(height_left, height_right))

        dst_pts = np.float32([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1]
        ])

        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped_img = cv2.warpPerspective(img, M, (max_width, max_height))

        try:
            name = self.txt_filename.text()
            ext = self.lbl_extension.text()
            if not name:
                name = "imagem_editada"
            
            filename = f"{name}{ext}"
            
            original_dir = os.path.dirname(self.original_path)
            save_path = os.path.join(original_dir, filename)
            
            cv2.imwrite(save_path, warped_img)
            QMessageBox.information(self, "Sucesso", f"Imagem salva em:\n{save_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OpenCVApp()
    window.show()
    sys.exit(app.exec_())
