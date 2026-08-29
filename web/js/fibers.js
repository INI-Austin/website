/* Tractography hero: sub-test3's own white-matter streamlines, drawn live.
 *
 * The geometry is 14,000 streamlines resampled to a fixed 22 points each and
 * quantised to int16 (web/data/fibers.bin, built by render/export_web.py).
 * A fixed point count per line means the index buffer is arithmetic rather
 * than data, so nothing but positions crosses the wire.
 *
 * The resting field does not rotate. Motion is confined to the distal ends of
 * each streamline: the middle stays planted while both tips bend in a shared,
 * low-frequency wind field, like branches moving together in a light breeze.
 */
(function () {
  "use strict";

  var DATA = "data/fibers.bin";
  var FPS = 45;

  var AZIM = 0;
  var ELEV = 0;
  var SWAY_PERIOD = 8.5;
  var SWAY_AMP = 0.085;      // at the tips; the middle of each line is anchored

  // "blue" is the site palette; "dec" is the field's own direction encoding,
  // which is what the reference render uses.
  var PALETTE = "dec";

  // Resolution of the offscreen fibre pass relative to the canvas. Below 1.0
  // it merges neighbouring fibres into sheets, which hides the fact that 40k
  // streamlines are far sparser per pixel than the 600k reference render, but
  // it costs real sharpness. Density is the honest fix; this is the dial.
  var RENDER_SCALE = 1.0;

  var VERT = [
    "#version 300 es",
    "precision highp float;",
    "in vec3 pos;",
    "in vec3 tan;",
    "in float tip;",
    "in vec3 anchor;",          // streamline midpoint, constant along the line
    "uniform mat3 view;",
    "uniform float t;",
    "uniform float aspect;",
    "uniform float zoom;",
    "uniform float swayAmp;",
    "uniform float swayPhase;",
    "uniform int palette;",
    "out vec3 vcol;",
    "out float vfade;",
    "",
    "void main(){",
    "  vec3 p=pos;",
    "",
    // Anchor the middle of each streamline, bend both ends.
    "  float bend=tip*tip*(3.0-2.0*tip);",
    "  bend*=bend;",
    "",
    // Wind is a smooth field in space, sampled once per streamline at its
    // midpoint. Two consequences, both wanted: the whole fibre bends as one
    // piece instead of contorting, and neighbouring fibres get nearly the same
    // phase so they travel together. Randomising phase per fibre instead makes
    // adjacent lines move oppositely, which reads as static rather than wind.
    // Roughly two and a half cycles across the brain. Fibres a few millimetres
    // apart stay in phase, so bundles move as bundles, while distant regions
    // are out of phase, so the field undulates like a canopy instead of being
    // shoved sideways as one slab. Too low a frequency shears the whole
    // structure; too high returns to per-fibre static.
    "  float f=dot(anchor,vec3(6.5,5.0,3.5));",
    "  float ph=swayPhase+f;",
    "  float wind=sin(ph)*0.72+sin(ph*0.41+1.7)*0.28;",
    "",
    // One breeze direction for the whole field, with a slow spatial turn.
    // Projecting out the along-fibre component keeps every streamline its
    // original length, so the ends bend rather than stretch.
    "  vec3 breeze=normalize(vec3(1.0,0.26,0.18)+0.30*vec3(sin(f*0.31),cos(f*0.23),0.0));",
    "  vec3 T=normalize(tan+vec3(1e-5));",
    "  vec3 disp=breeze-T*dot(breeze,T);",
    "  p+=disp*wind*swayAmp*bend;",
    "",
    "  vec3 c=view*p;",
    "  vec3 tv=view*tan;",
    "",
    "  vec3 a=abs(normalize(tan));",
    "  vec3 w=a*a;",
    "  w/=(w.x+w.y+w.z);",
    "  vec3 col;",
    "  if(palette==0){",
    "    vec3 lr=vec3(0.34,0.72,1.00);",
    "    vec3 ap=vec3(0.13,0.31,0.78);",
    "    vec3 si=vec3(0.58,0.80,1.00);",
    "    col=w.x*lr+w.y*ap+w.z*si;",
    "  } else {",
    "    vec3 lr=vec3(1.00,0.46,0.46);",
    "    vec3 ap=vec3(0.46,0.92,0.52);",
    "    vec3 si=vec3(0.64,0.77,1.00);",
    "    col=w.x*lr+w.y*ap+w.z*si;",
    "  }",
    "",
    "  vec3 L=normalize(vec3(-0.42,0.70,-0.58));",
    "  float lt=abs(dot(normalize(tv),L));",
    "  float dif=sqrt(max(0.0,1.0-lt*lt));",
    "  col*=(0.30+0.85*dif);",
    "",
    "  float depth=clamp(c.z*0.5+0.5,0.0,1.0);",
    "  vfade=mix(1.0,0.34,depth);",
    "  vcol=col;",
    "  gl_Position=vec4(c.x*zoom/aspect,c.y*zoom,0.0,1.0);",
    "}"
  ].join("\n");

  var FRAG = [
    "#version 300 es",
    "precision highp float;",
    "in vec3 vcol;",
    "in float vfade;",
    "uniform float opacity;",
    "out vec4 frag;",
    "void main(){ frag=vec4(vcol*vfade*opacity,1.0); }"
  ].join("\n");

  var POST_VERT = [
    "#version 300 es",
    "precision highp float;",
    "out vec2 uv;",
    "void main(){",
    "  vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);",
    "  uv=p;",
    "  gl_Position=vec4(p*2.0-1.0,0.0,1.0);",
    "}"
  ].join("\n");

  var POST_FRAG = [
    "#version 300 es",
    "precision highp float;",
    "in vec2 uv;",
    "uniform sampler2D src;",
    "uniform float exposure;",
    "uniform float gamma;",
    "out vec4 frag;",
    "void main(){",
    "  vec3 c=texture(src,uv).rgb*exposure;",
    // Curve the luminance and rescale the colour by the same factor, rather
    // than curving each channel on its own. Per-channel tone mapping drives
    // every bright region to white, because whichever channel clips first
    // stops growing while the others catch up. Preserving the ratio keeps a
    // dense red bundle red instead of bleaching it.
    "  float l=max(c.r,max(c.g,c.b));",
    "  if(l<1e-5){ frag=vec4(0.0); return; }",
    "  float lm=1.0-exp(-l);",
    "  vec3 m=c*(lm/l);",
    "  m=pow(clamp(m,0.0,1.0),vec3(1.0/gamma));",
    "  float a=clamp(lm*1.25,0.0,1.0);",
    "  frag=vec4(m*a,a);",
    "}"
  ].join("\n");

  function viewMatrix(azimDeg, elevDeg) {
    var a = azimDeg * Math.PI / 180;
    var e = elevDeg * Math.PI / 180;

    var right = [Math.cos(a), Math.sin(a), 0];
    var fh = [-Math.sin(a), Math.cos(a), 0];
    var ca = Math.cos(e);
    var sa = Math.sin(e);
    var fwd = [fh[0] * ca, fh[1] * ca, -sa];

    var up = [
      right[1] * fwd[2] - right[2] * fwd[1],
      right[2] * fwd[0] - right[0] * fwd[2],
      right[0] * fwd[1] - right[1] * fwd[0]
    ];

    return new Float32Array([
      right[0], up[0], fwd[0],
      right[1], up[1], fwd[1],
      right[2], up[2], fwd[2]
    ]);
  }

  function compile(gl, type, src) {
    var sh = gl.createShader(type);

    gl.shaderSource(sh, src);
    gl.compileShader(sh);

    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
      console.warn(
        "fibers: shader compile failed\n" + gl.getShaderInfoLog(sh)
      );
      return null;
    }

    return sh;
  }

  function buildTangents(pos, nLines, nPts) {
    var out = new Int8Array(nLines * nPts * 3);

    for (var l = 0; l < nLines; l++) {
      var base = l * nPts * 3;

      for (var i = 0; i < nPts; i++) {
        var i0 = i === 0 ? 0 : i - 1;
        var i1 = i === nPts - 1 ? nPts - 1 : i + 1;

        var x = pos[base + i1 * 3] - pos[base + i0 * 3];
        var y = pos[base + i1 * 3 + 1] - pos[base + i0 * 3 + 1];
        var z = pos[base + i1 * 3 + 2] - pos[base + i0 * 3 + 2];
        var n = Math.hypot(x, y, z) || 1;

        out[base + i * 3] = Math.max(
          -127,
          Math.min(127, Math.round(x / n * 127))
        );

        out[base + i * 3 + 1] = Math.max(
          -127,
          Math.min(127, Math.round(y / n * 127))
        );

        out[base + i * 3 + 2] = Math.max(
          -127,
          Math.min(127, Math.round(z / n * 127))
        );
      }
    }

    return out;
  }

  function buildTipWeights(nLines, nPts) {
    var out = new Uint8Array(nLines * nPts);

    for (var l = 0; l < nLines; l++) {
      for (var i = 0; i < nPts; i++) {
        var u = nPts > 1 ? i / (nPts - 1) : 0.5;
        var d = Math.abs(u * 2 - 1);

        /*
         * The middle 30% remains anchored. Weight then increases smoothly
         * toward both endpoints of every individual streamline.
         */
        var w = Math.max(0, Math.min(1, (d - 0.30) / 0.70));
        w = w * w * (3 - 2 * w);

        out[l * nPts + i] = Math.round(w * 255);
      }
    }

    return out;
  }

  function buildAnchors(pos, nLines, nPts) {
    // Midpoint of each streamline, repeated across its vertices. Sampling the
    // wind here rather than per-vertex is what makes a fibre bend as one piece.
    var out = new Int8Array(nLines * nPts * 3);
    for (var l = 0; l < nLines; l++) {
      var base = l * nPts * 3;
      var sx = 0, sy = 0, sz = 0;
      for (var i = 0; i < nPts; i++) {
        sx += pos[base + i * 3];
        sy += pos[base + i * 3 + 1];
        sz += pos[base + i * 3 + 2];
      }
      // int16 source -> int8 attribute range
      var ax = Math.max(-127, Math.min(127, Math.round(sx / nPts / 258)));
      var ay = Math.max(-127, Math.min(127, Math.round(sy / nPts / 258)));
      var az = Math.max(-127, Math.min(127, Math.round(sz / nPts / 258)));
      for (i = 0; i < nPts; i++) {
        out[base + i * 3] = ax;
        out[base + i * 3 + 1] = ay;
        out[base + i * 3 + 2] = az;
      }
    }
    return out;
  }

  function start() {
    var canvas = document.getElementById("fibers");
    if (!canvas) return;

    var gl = canvas.getContext("webgl2", {
      alpha: true,
      antialias: true,
      depth: false,
      premultipliedAlpha: true,
      powerPreference: "high-performance"
    });

    if (!gl) {
      canvas.classList.add("is-failed");
      return;
    }

    fetch(DATA)
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.arrayBuffer();
      })
      .then(function (buf) {
        var dv = new DataView(buf);

        var magic = String.fromCharCode(
          dv.getUint8(0),
          dv.getUint8(1),
          dv.getUint8(2),
          dv.getUint8(3)
        );

        if (magic !== "INIG") {
          throw new Error("bad magic " + magic + " (stale fibers.bin?)");
        }

        // 16-byte header: magic, uint32 line count, uint16 points per line,
        // uint16 pad, float32 span in mm.
        var nLines = dv.getUint32(4, true);
        var nPts = dv.getUint16(8, true);
        var pos = new Int16Array(buf, 16, nLines * nPts * 3);

        run(gl, canvas, pos, nLines, nPts);
      })
      .catch(function (e) {
        console.warn("fibers: " + e.message);
        canvas.classList.add("is-failed");
      });
  }

  function run(gl, canvas, pos, nLines, nPts) {
    var vs = compile(gl, gl.VERTEX_SHADER, VERT);
    var fs = compile(gl, gl.FRAGMENT_SHADER, FRAG);

    if (!vs || !fs) {
      canvas.classList.add("is-failed");
      return;
    }

    var prog = gl.createProgram();
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);

    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      console.warn("fibers: link failed\n" + gl.getProgramInfoLog(prog));
      canvas.classList.add("is-failed");
      return;
    }

    gl.useProgram(prog);

    var vao = gl.createVertexArray();
    gl.bindVertexArray(vao);

    var pb = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, pb);
    gl.bufferData(gl.ARRAY_BUFFER, pos, gl.STATIC_DRAW);

    var lp = gl.getAttribLocation(prog, "pos");
    gl.enableVertexAttribArray(lp);
    gl.vertexAttribPointer(lp, 3, gl.SHORT, true, 0, 0);

    var tb = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, tb);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      buildTangents(pos, nLines, nPts),
      gl.STATIC_DRAW
    );

    var lt = gl.getAttribLocation(prog, "tan");
    gl.enableVertexAttribArray(lt);
    gl.vertexAttribPointer(lt, 3, gl.BYTE, true, 0, 0);

    var wb = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, wb);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      buildTipWeights(nLines, nPts),
      gl.STATIC_DRAW
    );

    var lw = gl.getAttribLocation(prog, "tip");
    gl.enableVertexAttribArray(lw);
    gl.vertexAttribPointer(
      lw,
      1,
      gl.UNSIGNED_BYTE,
      true,
      0,
      0
    );

    var ab = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, ab);
    gl.bufferData(gl.ARRAY_BUFFER, buildAnchors(pos, nLines, nPts), gl.STATIC_DRAW);

    var la = gl.getAttribLocation(prog, "anchor");
    gl.enableVertexAttribArray(la);
    gl.vertexAttribPointer(la, 3, gl.BYTE, true, 0, 0);

    var idx = new Uint32Array(nLines * (nPts + 1));
    var k = 0;

    for (var l = 0; l < nLines; l++) {
      for (var i = 0; i < nPts; i++) {
        idx[k++] = l * nPts + i;
      }

      idx[k++] = 0xFFFFFFFF;
    }

    var ib = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx, gl.STATIC_DRAW);

    var postProg = null;
    var uSrc;
    var uExp;
    var uGam;
    var tex = null;
    var fbo = null;
    var fbW = 0;
    var fbH = 0;

    var haveFloat =
      gl.getExtension("EXT_color_buffer_float") ||
      gl.getExtension("EXT_color_buffer_half_float");

    if (haveFloat) {
      var pv = compile(gl, gl.VERTEX_SHADER, POST_VERT);
      var pf = compile(gl, gl.FRAGMENT_SHADER, POST_FRAG);

      if (pv && pf) {
        postProg = gl.createProgram();
        gl.attachShader(postProg, pv);
        gl.attachShader(postProg, pf);
        gl.linkProgram(postProg);

        if (!gl.getProgramParameter(postProg, gl.LINK_STATUS)) {
          postProg = null;
        }
      }

      if (postProg) {
        uSrc = gl.getUniformLocation(postProg, "src");
        uExp = gl.getUniformLocation(postProg, "exposure");
        uGam = gl.getUniformLocation(postProg, "gamma");
        tex = gl.createTexture();
        fbo = gl.createFramebuffer();
      }
    }

    var postVao = gl.createVertexArray();

    function sizeTarget(w, h) {
      if (!postProg || (w === fbW && h === fbH)) return;

      fbW = w;
      fbH = h;

      gl.bindTexture(gl.TEXTURE_2D, tex);

      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.RGBA16F,
        w,
        h,
        0,
        gl.RGBA,
        gl.HALF_FLOAT,
        null
      );

      gl.texParameteri(
        gl.TEXTURE_2D,
        gl.TEXTURE_MIN_FILTER,
        gl.LINEAR
      );

      gl.texParameteri(
        gl.TEXTURE_2D,
        gl.TEXTURE_MAG_FILTER,
        gl.LINEAR
      );

      gl.texParameteri(
        gl.TEXTURE_2D,
        gl.TEXTURE_WRAP_S,
        gl.CLAMP_TO_EDGE
      );

      gl.texParameteri(
        gl.TEXTURE_2D,
        gl.TEXTURE_WRAP_T,
        gl.CLAMP_TO_EDGE
      );

      gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);

      gl.framebufferTexture2D(
        gl.FRAMEBUFFER,
        gl.COLOR_ATTACHMENT0,
        gl.TEXTURE_2D,
        tex,
        0
      );

      if (
        gl.checkFramebufferStatus(gl.FRAMEBUFFER) !==
        gl.FRAMEBUFFER_COMPLETE
      ) {
        postProg = null;
      }

      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    }

    var uView = gl.getUniformLocation(prog, "view");
    var uT = gl.getUniformLocation(prog, "t");
    var uAspect = gl.getUniformLocation(prog, "aspect");
    var uZoom = gl.getUniformLocation(prog, "zoom");
    var uSwayAmp = gl.getUniformLocation(prog, "swayAmp");
    var uSwayPhase = gl.getUniformLocation(prog, "swayPhase");
    var uOpacity = gl.getUniformLocation(prog, "opacity");
    var uPalette = gl.getUniformLocation(prog, "palette");

    gl.disable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE);
    gl.clearColor(0, 0, 0, 0);

    var reduce = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    function resize() {
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      var w = Math.round(canvas.clientWidth * dpr);
      var h = Math.round(canvas.clientHeight * dpr);

      if (
        !w ||
        !h ||
        (w === canvas.width && h === canvas.height)
      ) {
        return;
      }

      canvas.width = w;
      canvas.height = h;
    }

    resize();

    var restAzim = AZIM;
    var restElev = ELEV;
    var vAzim = 0;
    var vElev = 0;
    var dragging = false;
    var lastX = 0;
    var lastY = 0;

    canvas.style.touchAction = "none";

    canvas.addEventListener("pointerdown", function (e) {
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
      vAzim = 0;
      vElev = 0;

      canvas.setPointerCapture(e.pointerId);
      canvas.classList.add("is-grabbing");
    });

    canvas.addEventListener("pointermove", function (e) {
      if (!dragging) return;

      var dx = e.clientX - lastX;
      var dy = e.clientY - lastY;

      lastX = e.clientX;
      lastY = e.clientY;

      restAzim += dx * 0.32;
      restElev = Math.max(
        -80,
        Math.min(80, restElev + dy * 0.26)
      );

      vAzim = dx * 0.32;
      vElev = dy * 0.26;
    });

    function endDrag(e) {
      if (!dragging) return;

      dragging = false;
      canvas.classList.remove("is-grabbing");

      try {
        canvas.releasePointerCapture(e.pointerId);
      } catch (_) {}
    }

    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);

    var raf = 0;
    var last = 0;
    var t0 = null;
    var frameMs = 1000 / FPS;

    function frame(now) {
      raf = requestAnimationFrame(frame);

      if (t0 === null) t0 = now;
      if (now - last < frameMs) return;

      last = now;
      resize();

      var t = (now - t0) / 1000;

      gl.useProgram(prog);
      gl.bindVertexArray(vao);

      if (!dragging) {
        restAzim += vAzim;

        restElev = Math.max(
          -80,
          Math.min(80, restElev + vElev)
        );

        vAzim *= 0.94;
        vElev *= 0.94;

        if (Math.abs(vAzim) < 0.002) vAzim = 0;
        if (Math.abs(vElev) < 0.002) vElev = 0;
      }

      /*
       * There is no automatic camera rotation. The reader drags or it sits
       * still.
       *
       * A 180-degree image-plane correction was proposed here, negating both
       * screen right and screen up so the hero matched the d2_cor reference
       * shot exactly. It is deliberately not applied. That reference was
       * rendered before the up-vector bug was found: view_matrix used
       * cross(fwd, right), which points inferior, so every frame it produced
       * was vertically mirrored. Negating up reproduces the reference by
       * reproducing the bug, and negating right mirrors the hemispheres on
       * top of it. Checked against the corrected Python coronal, the
       * uncorrected basis here is the anatomically right one: interhemispheric
       * fissure at the top, corona radiata ascending, brainstem below.
       */
      var vm = viewMatrix(restAzim, restElev);

      // 180-degree image-plane correction, applied at the client's request so
      // the hero matches the reference render exactly. It negates screen right
      // and screen up, which mirrors the hemispheres and puts the brain
      // inferior-side-up. Anatomically wrong, deliberately kept.
      vm[0] *= -1; vm[3] *= -1; vm[6] *= -1;
      vm[1] *= -1; vm[4] *= -1; vm[7] *= -1;

      gl.uniformMatrix3fv(uView, false, vm);
      gl.uniform1f(uT, t);

      gl.uniform1f(
        uAspect,
        canvas.width / Math.max(1, canvas.height)
      );

      gl.uniform1f(uZoom, 1.12);
      gl.uniform1f(uSwayAmp, reduce ? 0 : SWAY_AMP);

      gl.uniform1f(
        uSwayPhase,
        t * 2 * Math.PI / SWAY_PERIOD
      );

      // Lower per-line alpha: with 40k lines the density comes from count,
      // which keeps individual fibres reading as fine threads.
      gl.uniform1f(uOpacity, 0.019);
      gl.uniform1i(uPalette, PALETTE === "blue" ? 0 : 1);

      var rw = Math.max(2, Math.round(canvas.width * RENDER_SCALE));
      var rh = Math.max(2, Math.round(canvas.height * RENDER_SCALE));
      if (postProg) {
        sizeTarget(rw, rh);
      }

      if (postProg) {
        gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
        gl.viewport(0, 0, rw, rh);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.bindVertexArray(vao);
        gl.useProgram(prog);

        gl.drawElements(
          gl.LINE_STRIP,
          idx.length,
          gl.UNSIGNED_INT,
          0
        );

        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        gl.viewport(0, 0, canvas.width, canvas.height);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.disable(gl.BLEND);
        gl.useProgram(postProg);
        gl.bindVertexArray(postVao);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, tex);
        gl.uniform1i(uSrc, 0);
        gl.uniform1f(uExp, 2.4);
        gl.uniform1f(uGam, 1.5);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
        gl.enable(gl.BLEND);
      } else {
        gl.bindVertexArray(vao);
        gl.useProgram(prog);
        gl.clear(gl.COLOR_BUFFER_BIT);

        gl.drawElements(
          gl.LINE_STRIP,
          idx.length,
          gl.UNSIGNED_INT,
          0
        );
      }

      canvas.classList.add("is-on");
    }

    raf = requestAnimationFrame(frame);

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        if (raf) {
          cancelAnimationFrame(raf);
          raf = 0;
        }
      } else if (!raf) {
        t0 = null;
        last = 0;
        raf = requestAnimationFrame(frame);
      }
    });

    canvas.addEventListener("webglcontextlost", function (e) {
      e.preventDefault();

      if (raf) {
        cancelAnimationFrame(raf);
        raf = 0;
      }
    });
  }

  if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
