package io.github.russianranger.trasc;

/** Screen-independent placement and drag policy for the embedded client's floating controls. */
final class ClientOverlayPosition {
    static final class Point {
        final float x,y;
        Point(float x,float y){this.x=x;this.y=y;}
    }
    static final class Placement {
        final int gearLeft,gearTop,lookLeft,lookTop;
        Placement(int gearLeft,int gearTop,int lookLeft,int lookTop){this.gearLeft=gearLeft;this.gearTop=gearTop;this.lookLeft=lookLeft;this.lookTop=lookTop;}
    }
    static final class Area {
        final int left,top,right,bottom,gearWidth,gearHeight;
        Area(int width,int height,int insetLeft,int insetTop,int insetRight,int insetBottom,int margin,int gearWidth,int gearHeight){
            this.gearWidth=gearWidth;this.gearHeight=gearHeight;
            // If a transient window is smaller than a control, keep its origin visible.
            left=Math.min(Math.max(0,insetLeft+margin),Math.max(0,width-gearWidth));
            top=Math.min(Math.max(0,insetTop+margin),Math.max(0,height-gearHeight));
            right=Math.max(left,width-Math.max(0,insetRight+margin));
            bottom=Math.max(top,height-Math.max(0,insetBottom+margin));
        }
        int maxLeft(){return Math.max(left,right-gearWidth);}
        int maxTop(){return Math.max(top,bottom-gearHeight);}
        Point normalize(float gearLeft,float gearTop){
            return new Point(normalizeCoordinate(gearLeft,left,maxLeft(),1f),normalizeCoordinate(gearTop,top,maxTop(),0f));
        }
        Placement place(float normalX,float normalY,int lookWidth,int gap,boolean lookVisible){
            int x=left+Math.round((maxLeft()-left)*normalized(normalX,1f));
            int y=top+Math.round((maxTop()-top)*normalized(normalY,0f));
            int lookX=x,lookY=y;
            if(lookVisible){
                if(x-gap-lookWidth>=left)lookX=x-gap-lookWidth;
                else if(x+gearWidth+gap+lookWidth<=right)lookX=x+gearWidth+gap;
                else {
                    lookX=Math.max(left,Math.min(x,Math.max(left,right-lookWidth)));
                    if(y+gearHeight+gap+gearHeight<=bottom)lookY=y+gearHeight+gap;
                    else if(y-gap-gearHeight>=top)lookY=y-gap-gearHeight;
                    else lookY=top;
                }
            }
            return new Placement(x,y,lookX,lookY);
        }
    }
    static final class Drag {
        private final float threshold;
        private float downX,downY,startX,startY;
        private boolean active,dragging;
        Drag(float threshold){this.threshold=Math.max(1f,threshold);}
        void start(float x,float y,float gearLeft,float gearTop){downX=x;downY=y;startX=gearLeft;startY=gearTop;active=true;dragging=false;}
        boolean move(float x,float y){
            if(!active)return false;
            float dx=x-downX,dy=y-downY;
            if(dx*dx+dy*dy>threshold*threshold)dragging=true;
            return dragging;
        }
        Point position(float x,float y){return new Point(startX+x-downX,startY+y-downY);}
        boolean active(){return active;}
        boolean dragging(){return dragging;}
        boolean finish(){boolean click=active&&!dragging;cancel();return click;}
        void cancel(){active=false;dragging=false;}
    }
    static float normalized(float value,float fallback){return Float.isFinite(value)?Math.max(0f,Math.min(1f,value)):fallback;}
    private static float normalizeCoordinate(float coordinate,int min,int max,float fallback){return max>min?normalized((coordinate-min)/(max-min),fallback):fallback;}
    private ClientOverlayPosition(){}
}
