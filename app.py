from flask import Flask, request, jsonify, Response
from image_to_3d import image_to_3d
from material_analysis import analyse_materials

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

def serve_file(path):
    return Response(open(path, encoding="utf-8").read(), mimetype="text/html; charset=utf-8")

@app.route("/")
def home():
    return serve_file("home.html")

@app.route("/viewer")
def viewer():
    return serve_file("viewer.html")

@app.route("/image-to-3d", methods=["POST"])
def convert_image_to_3d():
    if "image" not in request.files:
        return jsonify({"error": "No file received"}), 400
    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    try:
        result = image_to_3d(file.read())
        result["material_analysis"] = analyse_materials(
            result["summary"], result["walls_2d"], result.get("rooms", [])
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/material-analysis", methods=["POST"])
def material_analysis_route():
    data = request.get_json(force=True)
    try:
        return jsonify(analyse_materials(data.get("summary", {}), data.get("walls_2d", [])))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
