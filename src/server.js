const express = require("express");
const multer = require("multer");
const { execFile } = require("child_process");
const fs = require("fs");
const path = require("path");

const app = express();
const port = 8000;

// ------------------------------
// Configuração do upload
// ------------------------------

const upload = multer({
  dest: "temp/",
  limits: {
    fileSize: 5 * 1024 * 1024, // 5 MB
  },
  fileFilter: (req, file, cb) => {
    const allowedTypes = ["image/jpeg", "image/png"];

    if (!allowedTypes.includes(file.mimetype)) {
      return cb(new Error("INVALID_FILE_TYPE"));
    }

    cb(null, true);
  },
});

// ------------------------------
// Helpers
// ------------------------------

function detectPlateFormat(plate) {
  const mercosul = /^[A-Z]{3}[0-9][A-Z][0-9]{2}$/;
  const oldBrazilian = /^[A-Z]{3}[0-9]{4}$/;

  if (mercosul.test(plate)) {
    return "MERCOSUL";
  }

  if (oldBrazilian.test(plate)) {
    return "BRAZILIAN_OLD";
  }

  return "UNKNOWN";
}

function removeTempFile(filePath) {
  if (!filePath) return;

  fs.unlink(filePath, (error) => {
    if (error) {
      console.error("Erro ao remover arquivo temporário:", error.message);
    }
  });
}

// ------------------------------
// Health check
// ------------------------------

app.get("/api/v1/health", (req, res) => {
  res.status(200).json({
    success: true,
    data: {
      status: "ok",
    },
  });
});

// ------------------------------
// Reconhecimento de placa
// ------------------------------

app.post(
  "/api/v1/plates/recognize",
  upload.single("image"),
  (req, res) => {
    const startTime = Date.now();

    if (!req.file) {
      return res.status(400).json({
        success: false,
        error: {
          code: "MISSING_FILE",
          message: "Nenhuma imagem foi enviada.",
        },
      });
    }

    const imagePath = req.file.path;

    const pythonScript = path.join(
      __dirname,
      "plate_recognition.py"
    );

    execFile(
      "python",
      [pythonScript, imagePath],
      {
        timeout: 15000,
      },
      (error, stdout, stderr) => {
        const processingTimeMs = Date.now() - startTime;

        removeTempFile(imagePath);

        if (error) {
          console.error("Erro Python:", error.message);
          console.error("stderr:", stderr);

          return res.status(500).json({
            success: false,
            error: {
              code: "PROCESSING_ERROR",
              message: "Ocorreu um erro ao processar a imagem.",
            },
            meta: {
              processingTimeMs,
            },
          });
        }

        const rawOutput = stdout.trim();

        if (!rawOutput) {
          return res.status(422).json({
            success: false,
            error: {
              code: "PLATE_NOT_FOUND",
              message: "Nenhuma placa foi identificada na imagem.",
            },
            meta: {
              processingTimeMs,
            },
          });
        }

        let result;

        try {
          result = JSON.parse(rawOutput);
        } catch {
          return res.status(500).json({
            success: false,
            error: {
              code: "INVALID_OCR_RESPONSE",
              message:
                "O serviço de reconhecimento retornou uma resposta inválida.",
            },
            meta: {
              processingTimeMs,
            },
          });
        }

        if (!result.plate) {
          return res.status(422).json({
            success: false,
            error: {
              code: "PLATE_NOT_FOUND",
              message: "Nenhuma placa válida foi reconhecida.",
            },
            meta: {
              processingTimeMs,
            },
          });
        }

        const normalizedPlate = String(result.plate)
          .toUpperCase()
          .replace(/[^A-Z0-9]/g, "");

        const format = detectPlateFormat(normalizedPlate);

        return res.status(200).json({
          success: true,
          data: {
            plate: normalizedPlate,
            format,
            confidence: result.confidence ?? null,
            detectedText: result.detectedText ?? normalizedPlate,
          },
          meta: {
            processingTimeMs,
          },
        });
      }
    );
  }
);

// ------------------------------
// Tratamento de erros do Multer
// ------------------------------

app.use((error, req, res, next) => {
  if (error instanceof multer.MulterError) {
    if (error.code === "LIMIT_FILE_SIZE") {
      return res.status(413).json({
        success: false,
        error: {
          code: "FILE_TOO_LARGE",
          message: "A imagem deve ter no máximo 5 MB.",
        },
      });
    }

    return res.status(400).json({
      success: false,
      error: {
        code: "UPLOAD_ERROR",
        message: "Ocorreu um erro durante o upload da imagem.",
      },
    });
  }

  if (error.message === "INVALID_FILE_TYPE") {
    return res.status(415).json({
      success: false,
      error: {
        code: "INVALID_FILE_TYPE",
        message: "Envie uma imagem no formato JPEG ou PNG.",
      },
    });
  }

  console.error(error);

  return res.status(500).json({
    success: false,
    error: {
      code: "INTERNAL_SERVER_ERROR",
      message: "Erro interno do servidor.",
    },
  });
});

// ------------------------------
// Rota inexistente
// ------------------------------

app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: {
      code: "ROUTE_NOT_FOUND",
      message: "Rota não encontrada.",
    },
  });
});

// ------------------------------
// Inicialização
// ------------------------------

app.listen(port, () => {
  console.log(`API rodando em http://localhost:${port}`);
});