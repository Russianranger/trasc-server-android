package io.github.russianranger.trasc;

public final class ClientOverlayPositionHostTest {
    public static void main(String[] args){
        ClientOverlayPosition.Area landscape=new ClientOverlayPosition.Area(1920,1080,0,0,0,0,12,48,48);
        ClientOverlayPosition.Placement initial=landscape.place(1f,0f,80,12,true);
        require(initial.gearLeft==1860&&initial.gearTop==12&&initial.lookLeft==1768&&initial.lookTop==12,"Default controls remain at upper right");
        ClientOverlayPosition.Placement hidden=landscape.place(1f,0f,80,12,false);
        require(hidden.gearLeft==initial.gearLeft&&hidden.gearTop==initial.gearTop,"Hiding tile must not move gear");
        ClientOverlayPosition.Point outside=landscape.normalize(-1000,10000);
        require(outside.x==0f&&outside.y==1f,"Dragging outside both edges clamps normalized coordinates");
        ClientOverlayPosition.Placement lowerLeft=landscape.place(outside.x,outside.y,80,12,true);
        require(lowerLeft.gearLeft==12&&lowerLeft.gearTop==1020&&lowerLeft.lookLeft==72,"Look tile follows on the available side");
        ClientOverlayPosition.Area rotated=new ClientOverlayPosition.Area(1280,720,24,18,30,40,12,48,48);
        ClientOverlayPosition.Placement quarter=rotated.place(.25f,.8f,80,12,true);
        ClientOverlayPosition.Point restored=rotated.normalize(quarter.gearLeft,quarter.gearTop);
        require(Math.abs(restored.x-.25f)<.001f&&Math.abs(restored.y-.8f)<.001f,"Normalized positions survive size and inset changes");
        safe(rotated,quarter,80,true);
        for(float x:new float[]{0f,.01f,.5f,.99f,1f})for(float y:new float[]{0f,.5f,1f})safe(rotated,rotated.place(x,y,80,12,true),80,true);
        ClientOverlayPosition.Placement corrupt=rotated.place(Float.NaN,Float.POSITIVE_INFINITY,80,12,true);
        require(corrupt.gearLeft==rotated.maxLeft()&&corrupt.gearTop==rotated.top,"Invalid stored position restores safe default");
        ClientOverlayPosition.Area narrow=new ClientOverlayPosition.Area(150,240,0,0,0,0,12,48,48);
        ClientOverlayPosition.Placement stacked=narrow.place(.5f,.5f,80,12,true);
        safe(narrow,stacked,80,true);
        require(stacked.lookTop!=stacked.gearTop,"Narrow windows stack controls without overlap");
        ClientOverlayPosition.Area tiny=new ClientOverlayPosition.Area(20,20,4,4,4,4,12,48,48);
        ClientOverlayPosition.Placement tinyPosition=tiny.place(.9f,.9f,80,12,false);
        require(tinyPosition.gearLeft==0&&tinyPosition.gearTop==0,"Undersized transient layouts retain visible gear origin");
        ClientOverlayPosition.Drag drag=new ClientOverlayPosition.Drag(10);
        drag.start(100,100,400,200);require(!drag.move(106,106)&&drag.finish(),"Jitter is an ordinary tap");
        drag.start(100,100,400,200);require(drag.move(112,100),"Deliberate motion begins a drag");
        ClientOverlayPosition.Point moved=drag.position(120,90);require(moved.x==420&&moved.y==190&&!drag.finish(),"Drag moves from original origin and never opens menu");
        drag.start(100,100,400,200);drag.move(130,110);drag.cancel();require(!drag.active()&&!drag.move(160,140)&&!drag.finish(),"Focus loss or multitouch cancellation cannot produce a stale click");
        System.out.println("PASS: per-world normalized overlay placement, safe insets/resize, stable hidden tile, edge placement, tap/drag threshold and cancellation");
    }
    private static void safe(ClientOverlayPosition.Area area,ClientOverlayPosition.Placement p,int lookWidth,boolean visible){
        require(p.gearLeft>=area.left&&p.gearLeft+area.gearWidth<=area.right&&p.gearTop>=area.top&&p.gearTop+area.gearHeight<=area.bottom,"Gear remains in safe area");
        if(visible){
            require(p.lookLeft>=area.left&&p.lookLeft+lookWidth<=area.right&&p.lookTop>=area.top&&p.lookTop+area.gearHeight<=area.bottom,"Look tile remains in safe area");
            require(p.lookLeft+lookWidth<=p.gearLeft||p.gearLeft+area.gearWidth<=p.lookLeft||p.lookTop+area.gearHeight<=p.gearTop||p.gearTop+area.gearHeight<=p.lookTop,"Controls do not overlap");
        }
    }
    private static void require(boolean pass,String message){if(!pass)throw new AssertionError(message);}
}
