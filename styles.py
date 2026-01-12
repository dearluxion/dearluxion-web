# ในไฟล์ styles.py
def get_css():
    return """
    <style>
        /* พื้นหลังและฟอนต์ */
        .stApp { background-color: #0E1117; color: #E6EDF3; font-family: 'Sarabun', sans-serif; }
        
        /* RGB Glow Border Animation */
        @keyframes rgb-border {
            0% { border-color: #ff0000; box-shadow: 0 0 5px #ff0000; }
            33% { border-color: #00ff00; box-shadow: 0 0 5px #00ff00; }
            66% { border-color: #0000ff; box-shadow: 0 0 5px #0000ff; }
            100% { border-color: #ff0000; box-shadow: 0 0 5px #ff0000; }
        }

        /* การ์ดโพสต์ (Minimal Glow) */
        .work-card-base {
            background: #161B22; padding: 20px;
            border-radius: 15px;
            border: 1px solid rgba(163, 112, 247, 0.3);
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4); transition: all 0.3s ease;
        }
        .work-card-base:hover {
            transform: translateY(-2px); box-shadow: 0 8px 30px rgba(163, 112, 247, 0.15);
            border-color: #A370F7;
        }
        
        /* ปุ่มกด (RGB Hover) */
        .stButton>button {
            border-radius: 25px; border: 1px solid #30363D;
            background-color: #21262D;
            color: white;
            transition: 0.3s;
            width: 100%;
            font-weight: 500;
        }
        .stButton>button:hover {
            border-color: #A370F7;
            color: #A370F7;
            background-color: #2b313a; box-shadow: 0 0 10px rgba(163, 112, 247, 0.2);
        }
        
        /* กล่องคอมเมนต์ */
        .comment-box {
            background-color: #0d1117; padding: 12px;
            border-radius: 10px;
            margin-top: 10px;
            border-left: 3px solid #A370F7;
            font-size: 13px;
        }
        .admin-comment-box {
            background: linear-gradient(90deg, #2b2100 0%, #1a1600 100%); padding: 12px;
            border-radius: 10px;
            margin-top: 10px;
            border: 1px solid #FFD700;
            font-size: 13px;
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.1);
        }

        /* ป้ายราคา */
        .price-tag {
            background: linear-gradient(45deg, #A370F7, #8a4bfa); color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 16px;
            display: inline-block;
            margin-bottom: 10px; box-shadow: 0 4px 15px rgba(163, 112, 247, 0.4);
        }
        
        /* Animation น้องไมล่า */
        @keyframes float {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-6px); }
        }
        .cute-guide {
            animation: float 3s infinite ease-in-out; background: linear-gradient(135deg, #FF9A9E, #FECFEF);
            padding: 10px 20px;
            border-radius: 30px;
            color: #555;
            font-weight: bold;
            text-align: center;
            margin-bottom: 15px; box-shadow: 0 5px 20px rgba(255, 154, 158, 0.4);
            cursor: pointer;
            border: 2px solid white;
        }

        /* Boss Billboard (RGB Minimal) */
        .boss-billboard {
            background: rgba(22, 27, 34, 0.8); backdrop-filter: blur(10px);
            border: 1px solid rgba(163, 112, 247, 0.5);
            border-radius: 20px;
            padding: 25px;
            text-align: center;
            margin-bottom: 30px;
            position: relative; box-shadow: 0 0 20px rgba(163, 112, 247, 0.15);
            overflow: hidden;
        }
        .boss-billboard::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: linear-gradient(90deg, #ff0000, #00ff00, #0000ff, #ff0000);
            background-size: 200% 100%;
            animation: rgb-move 5s linear infinite;
        }
        @keyframes rgb-move { 0% {background-position: 0% 50%;} 100% {background-position: 100% 50%;} }

        .billboard-icon { font-size: 28px; margin-bottom: 5px; }
        .billboard-text { font-size: 22px; font-weight: 700; color: #fff; letter-spacing: 0.5px; }
        .billboard-time { font-size: 10px; color: #8B949E; margin-top: 15px; text-transform: uppercase; letter-spacing: 1px; }

        a { color: #A370F7 !important; text-decoration: none; font-weight: 600; }
    </style>
    """