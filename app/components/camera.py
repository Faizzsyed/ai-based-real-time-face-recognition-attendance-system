"""Reusable premium in-layout biometric camera panel for Flet 0.86.5."""
from dataclasses import dataclass,field
import flet as ft
from app.components.ui import surface_card
from app.core.theme import ThemeTokens

def _indicator(label):
    return ft.Container(ft.Row([ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED,size=16,color="#94A3B8"),ft.Text(label,size=12,weight=ft.FontWeight.W_500)],spacing=6),padding=ft.Padding.symmetric(horizontal=10,vertical=7),bgcolor="#0F172A",border_radius=10,border=ft.Border.all(1,"#334155"),col={"xs":6,"sm":4,"md":2})

@dataclass
class CameraPanelState:
    image:ft.Image=field(default_factory=lambda:ft.Image(src=b"",fit=ft.BoxFit.CONTAIN,width=720,height=405,border_radius=18,gapless_playback=True,filter_quality=ft.FilterQuality.MEDIUM,visible=False))
    camera:str="stopped";face:str="waiting";face_size:str="waiting";lighting:str="waiting";sharpness:str="waiting";position:str="waiting";liveness:str="not_started";blink_count:int=0;required_blinks:int=1;capture_count:int=0;message:str="Camera is stopped.";has_preview:bool=False;last_valid_preview_frame:bytes|None=None
    camera_badge:ft.Container=field(default_factory=lambda:_indicator("Camera").content.controls[0])
    camera_label:ft.Text=field(default_factory=lambda:ft.Text("Camera Stopped",size=12,weight=ft.FontWeight.W_500))
    status_text:ft.ResponsiveRow=field(default_factory=lambda:ft.ResponsiveRow([_indicator(x) for x in ("One Face","Face Size","Lighting","Sharpness","Position","Liveness")],spacing=8,run_spacing=8))
    instruction_text:ft.Text=field(default_factory=lambda:ft.Text("Camera is stopped.",size=16,weight=ft.FontWeight.W_600,text_align=ft.TextAlign.CENTER))
    progress_text:ft.Text=field(default_factory=lambda:ft.Text("Blink 0 / 1  ·  Captures 0 / 3",size=12,color="#94A3B8"))
    retry_button:ft.TextButton=field(default_factory=lambda:ft.TextButton("Retry Liveness",icon=ft.Icons.REFRESH,visible=False))
    message_text:ft.Text=field(default_factory=lambda:ft.Text(""))
    placeholder:ft.Container=field(default_factory=lambda:ft.Container(ft.Column([ft.Icon(ft.Icons.FACE_RETOUCHING_NATURAL,size=58,color="#64748B"),ft.Text("Starting camera...",color="#CBD5E1",weight=ft.FontWeight.W_500)],horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=10),alignment=ft.Alignment.CENTER,expand=True))
    def _set_indicator(self,index,label,value):
        control=self.status_text.controls[index];row=control.content;good=value in {"good","one_face","passed","connected"};active=value in {"in_progress","starting"};row.controls[0].name=ft.Icons.CHECK_CIRCLE if good else ft.Icons.PENDING_OUTLINED if active else ft.Icons.RADIO_BUTTON_UNCHECKED;row.controls[0].color="#22C55E" if good else "#60A5FA" if active else "#94A3B8";control.border=ft.Border.all(1,"#1D4ED8" if active else "#166534" if good else "#334155");row.controls[1].value=label
    def sync(self):
        values=(("One Face",self.face),("Face Size",self.face_size),("Lighting",self.lighting),("Sharpness",self.sharpness),("Position",self.position),("Liveness",self.liveness))
        for index,(label,value) in enumerate(values):self._set_indicator(index,label,value)
        self.instruction_text.value=self.message;self.progress_text.value=f"Blink {self.blink_count} / {self.required_blinks}  ·  Captures {self.capture_count} / 3";self.message_text.value=self.message
        self.camera_badge.name=ft.Icons.FIBER_MANUAL_RECORD;self.camera_badge.color="#22C55E" if self.camera=="connected" else "#60A5FA" if self.camera=="starting" else "#EF4444" if self.camera in {"disconnected","unavailable"} else "#94A3B8"
        self.camera_label.value=f"Camera {self.camera.replace('_',' ').title()}"
    def accept_preview(self,encoded):
        if not encoded:return False
        self.last_valid_preview_frame=bytes(encoded);self.image.src=self.last_valid_preview_frame;first=not self.has_preview;self.has_preview=True;self.image.visible=True;self.placeholder.visible=False;return first
    def prepare_start(self):
        self.has_preview=False;self.image.visible=False;self.placeholder.visible=True;self.placeholder.content.controls[1].value="Starting camera..."

def _corner(left=None,top=None,right=None,bottom=None):
    return ft.Container(width=30,height=30,left=left,top=top,right=right,bottom=bottom,border=ft.Border(left=ft.BorderSide(3,"#60A5FA") if left is not None else ft.BorderSide(0,"transparent"),top=ft.BorderSide(3,"#60A5FA") if top is not None else ft.BorderSide(0,"transparent"),right=ft.BorderSide(3,"#60A5FA") if right is not None else ft.BorderSide(0,"transparent"),bottom=ft.BorderSide(3,"#60A5FA") if bottom is not None else ft.BorderSide(0,"transparent")),border_radius=6)

def build_camera_panel(state,tokens,on_start,on_stop,title="Live Camera",on_retry=None,mobile=False):
    state.retry_button.on_click=on_retry
    state.sync();guide=ft.Container(width=150 if mobile else 205,height=210 if mobile else 275,border=ft.Border.all(2,"#94A3B8"),border_radius=999,opacity=.75);preview=ft.Container(content=ft.Stack([state.placeholder,state.image,guide,_corner(left=18,top=18),_corner(right=18,top=18),_corner(left=18,bottom=18),_corner(right=18,bottom=18)],alignment=ft.Alignment.CENTER),height=280 if mobile else 405,alignment=ft.Alignment.CENTER,bgcolor="#07111F",border_radius=20,border=ft.Border.all(1,"#334155"),clip_behavior=ft.ClipBehavior.ANTI_ALIAS)
    header=ft.Row([ft.Column([ft.Text(title,size=21,weight=ft.FontWeight.BOLD),ft.Text("Secure biometric enrollment",size=12,color=tokens["text_secondary"])],spacing=2,expand=True),ft.Row([state.camera_badge,state.camera_label],spacing=5)],vertical_alignment=ft.CrossAxisAlignment.CENTER)
    instruction=ft.Container(ft.Column([state.instruction_text,state.progress_text],horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=5),padding=14,bgcolor=tokens["surface_secondary"],border_radius=14,alignment=ft.Alignment.CENTER)
    actions=[ft.Text("Android: select a recent camera photo below for secure server-side verification.",size=12,color=tokens["text_secondary"],text_align=ft.TextAlign.CENTER)] if mobile else [ft.FilledButton("Start Camera",icon=ft.Icons.VIDEOCAM_OUTLINED,on_click=on_start),state.retry_button,ft.OutlinedButton("Stop Camera",icon=ft.Icons.STOP_CIRCLE_OUTLINED,on_click=on_stop)]
    return surface_card(ft.Column([header,preview,state.status_text,instruction,ft.Row(actions,alignment=ft.MainAxisAlignment.CENTER,wrap=True)],spacing=14),tokens,key="live-camera-panel")
