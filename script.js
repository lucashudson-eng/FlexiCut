// --- Variáveis Globais ---
let imgElement = null; 
let originalFileName = "imagem";
let originalExt = ".jpg";

const container = document.getElementById('canvas-container');
const canvas = document.getElementById('main-canvas');
const ctx = canvas.getContext('2d');

let scale = 1.0;
let offsetX = 0;
let offsetY = 0;

let corners = [
    {x: 0.0, y: 0.0},
    {x: 1.0, y: 0.0},
    {x: 1.0, y: 1.0},
    {x: 0.0, y: 1.0}
];
const HANDLE_RADIUS = 8;

let isDraggingHandle = false;
let activeHandleIndex = -1;
let isPanning = false;
let lastMouseX = 0;
let lastMouseY = 0;

// --- Resize ---
function resizeCanvas() {
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    // Se tiver imagem desenha, senao limpa
    if (imgElement) draw();
    else {
        ctx.fillStyle = "#2d2d2d";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// --- Input ---
document.getElementById('file-input').addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) loadImageFile(e.target.files[0]);
});

container.addEventListener('dragover', (e) => { e.preventDefault(); });
container.addEventListener('drop', (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        const file = e.dataTransfer.files[0];
        if (file.type.startsWith('image/')) loadImageFile(file);
    }
});

function loadImageFile(file) {
    const parts = file.name.split('.');
    if (parts.length > 1) {
        originalExt = '.' + parts.pop();
        originalFileName = parts.join('.');
    } else {
        originalFileName = file.name;
        originalExt = '';
    }
    
    document.getElementById('filename-input').value = originalFileName + "_edited";
    
    const extSelect = document.getElementById('ext-select');
    if (extSelect) {
        const normExt = originalExt.toLowerCase();
        let matched = false;
        for (let i = 0; i < extSelect.options.length; i++) {
            if (extSelect.options[i].value === normExt) {
                extSelect.selectedIndex = i;
                matched = true;
                break;
            }
        }
        if (!matched) {
            extSelect.value = '.jpg';
        }
    }

    const reader = new FileReader();
    reader.onload = (evt) => {
        imgElement = new Image();
        imgElement.onload = () => {
            const loadingMsg = document.getElementById('loading-msg');
            if (loadingMsg) {
                loadingMsg.style.display = 'none';
            }
            resetView();
            draw();
        };
        imgElement.src = evt.target.result;
    };
    reader.readAsDataURL(file);
}

function resetView() {
    if (!imgElement) return;
    corners = [
        {x: 0.0, y: 0.0}, {x: 1.0, y: 0.0},
        {x: 1.0, y: 1.0}, {x: 0.0, y: 1.0}
    ];
    const wImg = imgElement.width;
    const hImg = imgElement.height;
    const wCan = canvas.width;
    const hCan = canvas.height;
    const scaleW = wCan / wImg;
    const scaleH = hCan / hImg;
    scale = Math.min(scaleW, scaleH) * 0.9;
    offsetX = (wCan - (wImg * scale)) / 2;
    offsetY = (hCan - (hImg * scale)) / 2;
}

// --- Draw ---
function draw() {
    ctx.fillStyle = "#2d2d2d";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (!imgElement) return;

    const wImg = imgElement.width;
    const hImg = imgElement.height;

    ctx.save();
    
    // Desenho da imagem
    const drawX = offsetX;
    const drawY = offsetY;
    const drawW = wImg * scale;
    const drawH = hImg * scale;
    
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(imgElement, drawX, drawY, drawW, drawH);

    // Desenho do Overlay
    const screenPoints = corners.map(p => ({
        x: offsetX + (p.x * wImg * scale),
        y: offsetY + (p.y * hImg * scale)
    }));

    // Sombra (Opcional, para melhorar visualização)
    ctx.beginPath();
    ctx.moveTo(screenPoints[0].x, screenPoints[0].y);
    for (let i = 1; i < screenPoints.length; i++) {
        ctx.lineTo(screenPoints[i].x, screenPoints[i].y);
    }
    ctx.closePath();
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#00ff00';
    ctx.stroke();

    ctx.fillStyle = '#00ff00';
    for (let p of screenPoints) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, HANDLE_RADIUS, 0, 2 * Math.PI);
        ctx.fill();
    }
    ctx.restore();
}

// --- Coords ---
function toImgNorm(screenX, screenY) {
    if (!imgElement) return {x:0, y:0};
    const wImg = imgElement.width;
    const hImg = imgElement.height;
    const imgPixelX = (screenX - offsetX) / scale;
    const imgPixelY = (screenY - offsetY) / scale;
    return {
        x: Math.max(0, Math.min(1, imgPixelX / wImg)),
        y: Math.max(0, Math.min(1, imgPixelY / hImg))
    };
}

function getScreenCoords(normP) {
    if (!imgElement) return {x:0, y:0};
    return {
        x: offsetX + (normP.x * imgElement.width * scale),
        y: offsetY + (normP.y * imgElement.height * scale)
    };
}

// --- Mouse ---
canvas.addEventListener('wheel', (e) => {
    if (!imgElement) return;
    e.preventDefault();
    const zoomFactor = 1.15;
    const factor = e.deltaY < 0 ? zoomFactor : (1 / zoomFactor);
    const mouseX = e.offsetX;
    const mouseY = e.offsetY;
    const oldImgX = (mouseX - offsetX) / scale;
    const oldImgY = (mouseY - offsetY) / scale;
    
    scale *= factor;
    offsetX = mouseX - (oldImgX * scale);
    offsetY = mouseY - (oldImgY * scale);
    draw();
});

canvas.addEventListener('mousedown', (e) => {
    if (!imgElement) return;
    const mouseX = e.offsetX;
    const mouseY = e.offsetY;

    if (e.button === 0) {
        let minDist = Infinity;
        let foundIndex = -1;
        const limitSq = (HANDLE_RADIUS * 2.5) ** 2;

        corners.forEach((p, i) => {
            const sc = getScreenCoords(p);
            const distSq = (sc.x - mouseX)**2 + (sc.y - mouseY)**2;
            if (distSq < limitSq && distSq < minDist) {
                minDist = distSq;
                foundIndex = i;
            }
        });

        if (foundIndex !== -1) {
            isDraggingHandle = true;
            activeHandleIndex = foundIndex;
            return;
        }
    }

    isPanning = true;
    lastMouseX = mouseX;
    lastMouseY = mouseY;
    container.style.cursor = 'grab';
});

window.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    if (isDraggingHandle && activeHandleIndex !== -1) {
        corners[activeHandleIndex] = toImgNorm(mouseX, mouseY);
        draw();
    } else if (isPanning) {
        const dx = mouseX - lastMouseX;
        const dy = mouseY - lastMouseY;
        offsetX += dx;
        offsetY += dy;
        lastMouseX = mouseX;
        lastMouseY = mouseY;
        draw();
    }
});

window.addEventListener('mouseup', () => {
    isDraggingHandle = false;
    activeHandleIndex = -1;
    isPanning = false;
    container.style.cursor = 'default';
});

canvas.addEventListener('contextmenu', (e) => e.preventDefault());

// --- Save / Core Logic ---
function saveImage() {
    if (!imgElement || !cvReady) {
        alert("Ops! O sistema de processamento ainda está carregando ou nenhuma imagem foi selecionada.");
        return;
    }

    try {
        let tempCanvas = document.createElement('canvas');
        tempCanvas.width = imgElement.width;
        tempCanvas.height = imgElement.height;
        let tempCtx = tempCanvas.getContext('2d');
        tempCtx.drawImage(imgElement, 0, 0);

        let imgData = tempCtx.getImageData(0, 0, imgElement.width, imgElement.height);
        let src = cv.matFromImageData(imgData);
        
        let w = src.cols;
        let h = src.rows;

        let srcTri = cv.matFromArray(4, 1, cv.CV_32FC2, [
            corners[0].x * w, corners[0].y * h,
            corners[1].x * w, corners[1].y * h,
            corners[2].x * w, corners[2].y * h,
            corners[3].x * w, corners[3].y * h
        ]);

        function dist(p1, p2) {
            return Math.sqrt(Math.pow(p1.x*w - p2.x*w, 2) + Math.pow(p1.y*h - p2.y*h, 2));
        }
        
        let widthTop = dist(corners[0], corners[1]);
        let widthBot = dist(corners[3], corners[2]);
        let maxWidth = Math.max(widthTop, widthBot);

        let heightLeft = dist(corners[0], corners[3]);
        let heightRight = dist(corners[1], corners[2]);
        let maxHeight = Math.max(heightLeft, heightRight);

        let dstTri = cv.matFromArray(4, 1, cv.CV_32FC2, [
            0, 0,
            maxWidth, 0,
            maxWidth, maxHeight,
            0, maxHeight
        ]);

        let M = cv.getPerspectiveTransform(srcTri, dstTri);
        let dst = new cv.Mat();
        let dsize = new cv.Size(maxWidth, maxHeight);
        
        cv.warpPerspective(src, dst, M, dsize, cv.INTER_LINEAR, cv.BORDER_CONSTANT, new cv.Scalar());

        cv.imshow(tempCanvas, dst); 

        let link = document.createElement('a');
        let inputName = document.getElementById('filename-input').value || 'imagem_editada';
        
        const extSelect = document.getElementById('ext-select');
        const chosenExt = extSelect ? extSelect.value : '.jpg';
        
        // Remove existing extension if it ends with any of the supported ones
        const supportedExts = ['.jpg', '.jpeg', '.png', '.webp'];
        let lowerName = inputName.toLowerCase();
        for (let ext of supportedExts) {
            if (lowerName.endsWith(ext)) {
                inputName = inputName.slice(0, -ext.length);
                break;
            }
        }
        inputName += chosenExt;
        link.download = inputName;
        
        let mime = 'image/jpeg';
        if (chosenExt === '.png') {
            mime = 'image/png';
        } else if (chosenExt === '.webp') {
            mime = 'image/webp';
        }
        
        link.href = tempCanvas.toDataURL(mime, 0.9);
        link.click();

        src.delete(); srcTri.delete(); dstTri.delete(); M.delete(); dst.delete();

    } catch (err) {
        console.error(err);
        alert("Erro técnico: " + err);
    }
}
