import os
import fitz
import re

print("=== RENOMBRADO FINAL ===\n")

base_dir = os.getcwd()

for root, dirs, files in os.walk(base_dir):

    for file in files:

        if file.lower().endswith(".pdf"):

            path = os.path.join(root, file)
            new_path = path

            try:
                # =========================
                # REGLA 1: POR CONTENIDO
                # =========================
                doc = fitz.open(path)
                text = ""

                for page in doc:
                    text += page.get_text("text")

                doc.close()

                text = text.upper()
                text = re.sub(r"\s+", "", text)

                if "NOTASDEEVOLUCION" in text:
                    new_path = os.path.join(root, "002.pdf")

                # =========================
                # REGLA 2: NOMBRE COMPLETO FIJO
                # =========================
                elif "OTROS" in file.upper():
                    new_path = os.path.join(root, "ORS.pdf")

                elif "PLANILLA" in file.upper():
                    new_path = os.path.join(root, "PI.pdf")

                # =========================
                # EJECUTAR CAMBIO
                # =========================
                if new_path != path:

                    if not os.path.exists(new_path):
                        os.rename(path, new_path)
                        print("✓ Renombrado:", path, "->", new_path)
                    else:
                        print("⚠ Ya existe:", new_path)

                else:
                    print(" - Sin cambios:", path)

            except Exception as e:
                print("X Error:", path)

print("\nTERMINADO")