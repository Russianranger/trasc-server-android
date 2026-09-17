package io.github.russianranger.trasc;

import android.app.*;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.util.*;

/** The same saved profile as the Client tab, edited without closing the game. */
final class ControllerDialog {
    private final Activity activity;
    private final ControllerManager controller;
    private final Runnable dismissed;
    private JSONObject draft;
    private LinearLayout root,rows;
    private Spinner modifier,layer;
    private EditText deadzone,speed;
    ControllerDialog(Activity activity,ControllerManager controller,Runnable dismissed){this.activity=activity;this.controller=controller;this.dismissed=dismissed;}
    private TextView label(String text){TextView v=new TextView(activity);v.setText(text);v.setPadding(8,12,8,4);root.addView(v);return v;}
    private Spinner spinner(List<String> choices){Spinner s=new Spinner(activity);s.setAdapter(new ArrayAdapter<>(activity,android.R.layout.simple_spinner_dropdown_item,choices));root.addView(s);return s;}
    void show(){
        try{draft=controller.state();}catch(JSONException e){dismissed.run();return;}
        root=new LinearLayout(activity);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(20,8,20,12);
        label("Presets use EQ defaults. Right stick: pointer. Hold R2: camera. L1: alternate hotbar layer. Changes apply only when saved.");
        Spinner preset=spinner(Arrays.asList("EQ adventure / hotbars","EQ spell gems","EQ inventory / cursor","Previous bindings"));
        Button apply=new Button(activity);apply.setText("Apply preset to editor");root.addView(apply);
        label("Hold for alternate bindings (consumes the selected button)");
        List<String> mods=new ArrayList<>();mods.add("None");mods.addAll(ControllerInput.SOURCES.subList(0,12));modifier=spinner(mods);
        label("Edit layer");layer=spinner(Arrays.asList("Normal bindings","While modifier is held"));
        label("Stick deadzone (0.05–0.80)");deadzone=new EditText(activity);deadzone.setInputType(8194);root.addView(deadzone);
        label("Pointer speed (50–2500 pixels/sec)");speed=new EditText(activity);speed.setInputType(2);root.addView(speed);
        rows=new LinearLayout(activity);rows.setOrientation(LinearLayout.VERTICAL);root.addView(rows);
        Runnable fill=()->{modifier.setSelection(mods.indexOf(draft.optString("modifier","None")));deadzone.setText(draft.optString("deadzone"));speed.setText(draft.optString("sensitivity"));render();};
        apply.setOnClickListener(v->{try{String name=new String[]{"adventure","spells","inventory","legacy"}[preset.getSelectedItemPosition()];draft=ControllerManager.preset(name);fill.run();}catch(JSONException ignored){}});
        layer.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){public void onItemSelected(AdapterView<?> p,View v,int pos,long id){render();}public void onNothingSelected(AdapterView<?> p){}});
        fill.run();ScrollView scroll=new ScrollView(activity);scroll.addView(root);
        AlertDialog dialog=new AlertDialog.Builder(activity).setTitle("Controller mappings").setView(scroll).setPositiveButton("Save",null).setNegativeButton("Cancel",null).create();
        dialog.setOnDismissListener(d->dismissed.run());dialog.show();
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{try{
            draft.put("modifier",modifier.getSelectedItem().toString()).put("deadzone",Double.parseDouble(deadzone.getText().toString())).put("sensitivity",Double.parseDouble(speed.getText().toString()));
            controller.configure(draft,true);dialog.dismiss();
        }catch(Exception e){Toast.makeText(activity,e.getMessage(),Toast.LENGTH_LONG).show();}});
    }
    private void render(){
        if(rows==null)return;rows.removeAllViews();boolean alternate=layer.getSelectedItemPosition()==1;
        JSONObject map=draft.optJSONObject(alternate?"shifted":"bindings");if(map==null)return;
        List<String> choices=new ArrayList<>();if(alternate)choices.add("Inherit");choices.addAll(ControllerInput.ACTIONS);
        for(String source:ControllerInput.SOURCES){TextView label=new TextView(activity);label.setText(source);rows.addView(label);
            Spinner s=new Spinner(activity);s.setContentDescription(source+" "+(alternate?"modifier":"normal")+" binding");s.setAdapter(new ArrayAdapter<>(activity,android.R.layout.simple_spinner_dropdown_item,choices));s.setSelection(Math.max(0,choices.indexOf(map.optString(source))));rows.addView(s);
            s.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){public void onItemSelected(AdapterView<?> p,View v,int pos,long id){try{map.put(source,choices.get(pos));}catch(JSONException ignored){}}public void onNothingSelected(AdapterView<?> p){}});
        }
    }
}
