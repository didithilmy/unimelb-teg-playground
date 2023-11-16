using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor;
using EasyRoads3Dv3;

[CustomEditor(typeof(CustomTrafficSpawner))]
public class CustomTrafficSpawnerEditor : Editor
{

    private GameObject trafficLightGameObject = null;
    private int fromLane = 0, toLane = 0;
    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();
        CustomTrafficSpawner customTrafficSpawner = (CustomTrafficSpawner)target;
        if (GUILayout.Button("Add car"))
        {
            customTrafficSpawner.AddCar();
        }
    }
}
