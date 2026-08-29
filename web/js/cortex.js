/* Cortical backdrop: sub-test3's own pial surface, relit every frame.
 *
 * This is not a procedural imitation of cortex. web/data/cortex-relight.png
 * holds the real surface baked by render/bake_cortex_tile.py, storing the
 * camera-space normal in RGB and sulcal depth in alpha rather than a colour.
 * Shipping geometry instead of a picture is what makes the lighting movable:
 * the shader can put the light wherever it likes, whenever it likes, and the
 * folds respond as the actual surface would.
 *
 * The tile was cropped from well inside the silhouette and its wrap-around
 * overlap blended away, so it repeats with no edge. Vertical travel is
 * therefore endless and seam-free, and page scroll feeds the same offset.
 *
 * Two slow, out-of-phase cycles keep it alive without ever snapping: the key
 * light orbits, and the palette drifts between a cool navy and a warmer steel.
 * Both periods are long and mutually prime enough that the loop is not legible.
 */
(function () {
  "use strict";

  var SRC = "data/cortex-relight.png";
  var FPS = 30;
  var SCALE = 0.85;      // render slightly below CSS resolution
  var TILES = 1.55;      // tile repeats across the viewport width
  var DRIFT = 0.0075;    // tiles per second of vertical travel

  var VERT = [
    "#version 300 es",
    "precision highp float;",
    "out vec2 uv;",
    "void main(){",
    "  vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);",
    "  uv=p; gl_Position=vec4(p*2.0-1.0,0.0,1.0);",
    "}"
  ].join("\n");

  var FRAG = [
    "#version 300 es",
    "precision highp float;",
    "in vec2 uv;",
    "uniform sampler2D cortex;",
    "uniform vec2 res;",
    "uniform float t;",
    "uniform float scroll;",
    "out vec4 frag;",
    "",
    "void main(){",
    "  float aspect=res.x/max(res.y,1.0);",
    "  vec2 p=vec2(uv.x*aspect,uv.y)*" + "TILESCALE" + ";",
    "  p.y-=scroll;",
    "",
    "  vec4 T=texture(cortex,p);",
    "  vec3 n=normalize(T.xyz*2.0-1.0);",
    "  float sulc=T.w;",                     // 1 deep in a sulcus, 0 on a crown
    "",
    // The key light orbits slowly. L is the direction TO the light; the bake
    // stored camera-space normals with the viewer down -z, so a light that
    // reaches front-facing folds must also carry a negative z.
    "  float a=t*0.085;",
    "  vec3 L=normalize(vec3(cos(a)*0.58,0.34+0.26*sin(a*0.73),-0.72));",
    "  float dif=clamp(dot(n,L),0.0,1.0);",
    "",
    // A dim fill from the opposite side keeps sulci from going flat black.
    "  vec3 F=normalize(vec3(-L.x,-0.30,-0.86));",
    "  float fill=clamp(dot(n,F),0.0,1.0)*0.30;",
    "",
    "  vec3 V=vec3(0.0,0.0,-1.0);",
    "  vec3 H=normalize(L+V);",
    "  float spec=pow(clamp(dot(n,H),0.0,1.0),26.0);",
    "  float rim=pow(1.0-clamp(dot(n,V),0.0,1.0),2.6);",
    "",
    // Sulcal depth doubles as occlusion: creases sit in shadow.
    "  float ao=mix(1.0,0.46,sulc);",
    "",
    // Palette drifts on a separate, slower cycle so the colour change never
    // lines up with the light and never reads as a loop.
    "  float w=0.5+0.5*sin(t*0.043);",
    "  vec3 deepC=mix(vec3(3.0,8.0,22.0),vec3(5.0,12.0,26.0),w)/255.0;",
    "  vec3 midC =mix(vec3(16.0,44.0,86.0),vec3(22.0,52.0,80.0),w)/255.0;",
    "  vec3 hiC  =mix(vec3(122.0,196.0,240.0),vec3(150.0,205.0,228.0),w)/255.0;",
    "",
    "  float lum=clamp(0.16+0.82*dif+fill,0.0,1.0)*ao;",
    "  vec3 col=lum<0.5?mix(deepC,midC,lum/0.5):mix(midC,hiC,(lum-0.5)/0.5);",
    "  col+=hiC*spec*ao*0.55;",
    "  col+=vec3(0.30,0.62,0.86)*rim*0.10*ao;",
    "",
    "  vec2 v=(uv-0.5)*2.0;",
    "  col*=clamp(1.04-0.26*dot(v,v),0.0,1.2);",
    "  frag=vec4(col,1.0);",
    "}"
  ].join("\n").replace("TILESCALE", TILES.toFixed(3));

  function compile(gl, type, src) {
    var sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
      console.warn("cortex: shader failed\n" + gl.getShaderInfoLog(sh));
      return null;
    }
    return sh;
  }

  function start() {
    var canvas = document.createElement("canvas");
    canvas.className = "cortex-canvas";
    canvas.setAttribute("aria-hidden", "true");

    var gl = canvas.getContext("webgl2", {
      alpha: false, antialias: false, depth: false,
      stencil: false, powerPreference: "low-power"
    });
    if (!gl) return;

    var vs = compile(gl, gl.VERTEX_SHADER, VERT);
    var fs = compile(gl, gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) return;
    var prog = gl.createProgram();
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      console.warn("cortex: link failed\n" + gl.getProgramInfoLog(prog));
      return;
    }
    gl.useProgram(prog);
    gl.bindVertexArray(gl.createVertexArray());

    var uRes = gl.getUniformLocation(prog, "res");
    var uT = gl.getUniformLocation(prog, "t");
    var uScroll = gl.getUniformLocation(prog, "scroll");
    gl.uniform1i(gl.getUniformLocation(prog, "cortex"), 0);

    var tex = gl.createTexture();
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, tex);
    // One blue pixel until the map arrives, so nothing flashes.
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE,
                  new Uint8Array([128, 128, 0, 0]));

    var img = new Image();
    img.onload = function () {
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.generateMipmap(gl.TEXTURE_2D);
      canvas.classList.add("is-on");
    };
    img.onerror = function () { console.warn("cortex: could not load " + SRC); };
    img.src = SRC;

    document.body.appendChild(canvas);

    function resize() {
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      var w = Math.max(1, Math.round(window.innerWidth * dpr * SCALE));
      var h = Math.max(1, Math.round(window.innerHeight * dpr * SCALE));
      if (w === canvas.width && h === canvas.height) return;
      canvas.width = w;
      canvas.height = h;
      gl.viewport(0, 0, w, h);
      gl.uniform2f(uRes, w, h);
    }
    resize();

    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var raf = 0, last = 0, t0 = null, frameMs = 1000 / FPS;

    function frame(now) {
      raf = requestAnimationFrame(frame);
      if (t0 === null) t0 = now;
      if (now - last < frameMs) return;
      last = now;
      var t = reduce ? 0 : (now - t0) / 1000;
      gl.uniform1f(uT, t);
      gl.uniform1f(uScroll, t * DRIFT + (window.scrollY || 0) * 0.00042);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
    raf = requestAnimationFrame(frame);

    var rt;
    window.addEventListener("resize", function () {
      clearTimeout(rt);
      rt = setTimeout(resize, 180);
    }, { passive: true });

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        if (raf) { cancelAnimationFrame(raf); raf = 0; }
      } else if (!raf) {
        t0 = null; last = 0;
        raf = requestAnimationFrame(frame);
      }
    });

    canvas.addEventListener("webglcontextlost", function (e) {
      e.preventDefault();
      if (raf) { cancelAnimationFrame(raf); raf = 0; }
      canvas.classList.remove("is-on");
    });
  }

  if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
