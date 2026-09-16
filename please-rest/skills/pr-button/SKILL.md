---
name: pr-button
description: ButtonComponent base class and subclass pattern for write operations in Grasshopper REST API plugins
---

# Skill: Button component

Two parts: the base class that lives in `Utilities/ButtonComponent.cs` copied verbatim into every plugin, and the subclass pattern for every write operation component.

---

## Part 1 — ButtonComponent.cs (copy verbatim, never modify)

```csharp
using Grasshopper.Kernel;
using Grasshopper.Kernel.Attributes;
using Grasshopper.GUI.Canvas;
using Grasshopper.GUI;
using System;
using System.Drawing;
using System.Windows.Forms;

namespace [PluginName]
{
    /// <summary>
    /// Base class for any component that needs a clickable button.
    /// Subclasses override ButtonLabel and SolveInstance to provide
    /// their own label text and trigger logic.
    /// </summary>
    public abstract class ButtonComponent : GH_Component
    {
        // Pending press (set by the button, consumed by the next solve pass)
        private bool _pending = false;
        // True only for the duration of the solve pass that consumed the press
        private bool _armed = false;

        protected ButtonComponent(string name, string nickname, string description, string category, string subcategory)
            : base(name, nickname, description, category, subcategory)
        { }

        /// <summary>Text shown on the button.</summary>
        public abstract string ButtonLabel { get; }

        /// <summary>
        /// True during the solve pass immediately after the button was pressed.
        /// Consumed in BeforeSolveInstance, so a press is never carried into a later,
        /// unrelated recompute — even when SolveInstance itself does not run (missing inputs).
        /// </summary>
        protected bool IsTriggered => _armed;

        // ---- Last result cache (survives recomputes and .gh save/reopen) ----

        /// <summary>Status text from the last button-driven call ("" if never run).</summary>
        protected string LastStatus { get; set; } = "";

        /// <summary>Raw response body from the last button-driven call ("" if never run).</summary>
        protected string LastResponse { get; set; } = "";

        /// <summary>
        /// Called on every solve where the button was NOT pressed. Re-emits the cached result so
        /// downstream components keep their data. Base sets output 0 (Status) and output 1
        /// (Response); override to re-derive any parsed outputs from LastResponse, calling base first.
        /// </summary>
        protected virtual void EmitLastResult(IGH_DataAccess DA)
        {
            if (string.IsNullOrEmpty(LastStatus) && string.IsNullOrEmpty(LastResponse))
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "Press \"" + ButtonLabel + "\" to run.");
                return;
            }
            if (Params.Output.Count > 0) DA.SetData(0, LastStatus);
            if (Params.Output.Count > 1) DA.SetData(1, LastResponse);
        }

        /// <summary>Call base.BeforeSolveInstance() if you override this.</summary>
        protected override void BeforeSolveInstance()
        {
            _armed = _pending;     // consume the press for this pass only
            _pending = false;
            base.BeforeSolveInstance();
        }

        /// <summary>Call base.AfterSolveInstance() if you override this.</summary>
        protected override void AfterSolveInstance()
        {
            _armed = false;
            base.AfterSolveInstance();
        }

        // ---- Persist the cache in the .gh file ----

        public override bool Write(GH_IO.Serialization.GH_IWriter writer)
        {
            writer.SetString("pr_last_status", LastStatus ?? "");
            writer.SetString("pr_last_response", LastResponse ?? "");
            return base.Write(writer);
        }

        public override bool Read(GH_IO.Serialization.GH_IReader reader)
        {
            string s = "", r = "";
            if (reader.ItemExists("pr_last_status")) reader.TryGetString("pr_last_status", ref s);
            if (reader.ItemExists("pr_last_response")) reader.TryGetString("pr_last_response", ref r);
            LastStatus = s;
            LastResponse = r;
            return base.Read(reader);
        }

        // ---- Button trigger ----

        public void TriggerButton()
        {
            _pending = true;
            ExpireSolution(true);
        }

        // ---- Custom attributes ----

        public override void CreateAttributes()
        {
            m_attributes = new ButtonAttributes(this);
        }
    }

    // ---- Reusable button attributes ----

    public class ButtonAttributes : GH_ComponentAttributes
    {
        private RectangleF _buttonBounds;

        private ButtonComponent ButtonOwner => (ButtonComponent)Owner;

        public ButtonAttributes(ButtonComponent owner) : base(owner) { }

        protected override void Layout()
        {
            base.Layout();

            float padding = 8f;
            float buttonH = 20f;
            float bottomMargin = 6f;

            var expanded = Bounds;
            expanded.Height += buttonH + bottomMargin * 2;
            Bounds = expanded;

            _buttonBounds = new RectangleF(
                Bounds.Left + padding,
                Bounds.Bottom - buttonH - bottomMargin,
                Bounds.Width - padding * 2,
                buttonH
            );
        }

        protected override void Render(GH_Canvas canvas, Graphics graphics, GH_CanvasChannel channel)
        {
            base.Render(canvas, graphics, channel);

            if (channel == GH_CanvasChannel.Objects)
            {
                var fillColor = Color.FromArgb(210, 38, 38, 38);
                var borderColor = Color.FromArgb(255, 95, 95, 95);
                var textColor = Color.FromArgb(255, 185, 185, 185);

                using (var brush = new SolidBrush(fillColor))
                using (var pen = new Pen(borderColor, 0.8f))
                using (var tBrush = new SolidBrush(textColor))
                using (var font = new Font("Arial", 6f, FontStyle.Regular))
                {
                    var rect = Rectangle.Round(_buttonBounds);

                    using (var path = RoundedRect(rect, 4))
                    {
                        graphics.FillPath(brush, path);
                        graphics.DrawPath(pen, path);
                    }

                    var sf = new StringFormat
                    {
                        Alignment = StringAlignment.Center,
                        LineAlignment = StringAlignment.Center,
                        Trimming = StringTrimming.EllipsisCharacter
                    };

                    graphics.DrawString(ButtonOwner.ButtonLabel, font, tBrush, _buttonBounds, sf);
                }
            }
        }

        public override GH_ObjectResponse RespondToMouseDown(GH_Canvas sender, GH_CanvasMouseEvent e)
        {
            if (e.Button == MouseButtons.Left && _buttonBounds.Contains(e.CanvasLocation))
            {
                ButtonOwner.TriggerButton();
                return GH_ObjectResponse.Handled;
            }
            return base.RespondToMouseDown(sender, e);
        }

        private static System.Drawing.Drawing2D.GraphicsPath RoundedRect(Rectangle rect, int radius)
        {
            int d = radius * 2;
            var path = new System.Drawing.Drawing2D.GraphicsPath();
            path.AddArc(rect.X, rect.Y, d, d, 180, 90);
            path.AddArc(rect.Right - d, rect.Y, d, d, 270, 90);
            path.AddArc(rect.Right - d, rect.Bottom - d, d, d, 0, 90);
            path.AddArc(rect.X, rect.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }
    }
}
```

---

## Part 2 — Subclass pattern (every write operation component)

```csharp
using System;
using System.Threading.Tasks;
using Grasshopper.Kernel;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace [PluginName]
{
    // [One line describing what this component does.]
    public class [Name]Component : ButtonComponent
    {
        public [Name]Component()
            : base("[Display Name]", "[Nickname]",
                "[One sentence description ending with a period]",
                PluginUtilities.TabName, PluginUtilities.Category[XX][Descriptor])
        { }

        public override string ButtonLabel => "[Label]";

        protected override void RegisterInputParams(GH_InputParamManager pManager)
        {
            // one pManager.Add per param, default value always supplied
        }

        protected override void RegisterOutputParams(GH_OutputParamManager pManager)
        {
            // output 0 is always Status (S), output 1 is always Response (R), then parsed fields
        }

        protected override void SolveInstance(IGH_DataAccess DA)
        {
            if (!IsTriggered) { EmitLastResult(DA); return; }

            // 1. Declare variables with defaults
            // 2. DA.GetData calls
            // 3. Guard clauses  (an early return here is safe — the press is already consumed)
            // 4. Logic — sync call site, see pr-component "Calling the client":
            //    var client = new [PluginName]Client(token);
            //    var (ok, json, err) = Task.Run(() => client.[Action]Async(...)).GetAwaiter().GetResult();
            //    LastStatus   = ok ? "OK" : "Error: " + err;
            //    LastResponse = ok ? json : "";
            //    if (!ok) AddRuntimeMessage(GH_RuntimeMessageLevel.Error, err);
            // 5. DA.SetData calls — DA.SetData(0, LastStatus); DA.SetData(1, LastResponse); parsed fields…
        }

        // Re-emit parsed outputs from the cached response on non-triggered solves
        protected override void EmitLastResult(IGH_DataAccess DA)
        {
            base.EmitLastResult(DA);                       // Status + Response
            if (string.IsNullOrEmpty(LastResponse)) return;
            try
            {
                var parsed = JObject.Parse(LastResponse);
                DA.SetData(2, (string)parsed["id"]);       // one line per parsed output
            }
            catch (JsonException) { /* non-JSON response — Status/Response already set */ }
        }

        protected override System.Drawing.Bitmap Icon => Properties.Resources.[ResourceName];
        public override Guid ComponentGuid => new Guid("[UNIQUE GUID]");
    }
}
```

Rules:
- `ButtonComponent.cs` is copied verbatim — only the namespace changes to match the plugin
- Subclasses override `ButtonLabel`, `RegisterInputParams`, `RegisterOutputParams`, `SolveInstance`,
  and `EmitLastResult` (only when the component has parsed outputs beyond Status/Response)
- `if (!IsTriggered) { EmitLastResult(DA); return; }` is always the first line of `SolveInstance` —
  a bare `return` would blank every output on any upstream recompute, file open, or F5, and knock the
  whole downstream chain to null until the button is pressed again
- After every button-driven call, set `LastStatus` / `LastResponse` **before** the `DA.SetData` calls —
  they are what the next non-triggered solve re-emits and what `Write`/`Read` persist into the `.gh`
- Output 0 is always `Status` (`S`), output 1 is always `Response` (`R`) — `EmitLastResult` in the
  base relies on these indices
- The press is consumed in `BeforeSolveInstance`, so a guard-clause early return (missing input) does
  **not** leave a stale trigger that fires the HTTP call on the next unrelated recompute
- Button colors are defined once in `ButtonAttributes.Render` — never per subclass
- `SolveInstance` still follows the same 5-step order as a standard component; the HTTP call uses the
  same sync call-site pattern as `pr-component`
