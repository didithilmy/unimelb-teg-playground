using System.Collections.Generic;
using UnityEngine;
using EasyRoads3Dv3;
using Michsky.MUIP;
using System;
using System.Linq;
using ITS.Utils;
using UnityEngine.EventSystems;
using System.Reflection.Emit;

public class RoadBuilderUIFlex : MonoBehaviour
{
    public CustomDropdown elementPickerDropdown;
    public ButtonManager startButton, stopButton;
    public Plane plane;

    private bool dragging = false;
    private Vector3 endCoord;
    private ERRoad currentRoad, currentFootpath;
    private GameObject currentTrafficLight;
    private CustomTrafficSpawner currentTrafficSpawner;
    private int rotationDegree = 0;
    private Collider coll;
    private RoadBuilderFlex roadBuilder;

    void Start()
    {
        coll = GetComponent<Collider>();
        roadBuilder = GetComponent<RoadBuilderFlex>();

        startButton.onClick.AddListener(roadBuilder.StartSimulation);
        stopButton.onClick.AddListener(roadBuilder.StopSimulation);
    }

    void Update()
    {
        Vector3? coord = GetMouseWorldCoord();
        if (coord != null)
        {
            endCoord = SnapToGrid((Vector3)coord);
            if (dragging)
            {
                if (currentRoad != null)
                {
                    roadBuilder.UpdateRoadEndCoord(currentRoad, endCoord);
                }
                else if (currentFootpath != null)
                {
                    roadBuilder.UpdateFootpathEndCoord(currentFootpath, endCoord);
                }
                else if (currentTrafficLight != null)
                {
                    roadBuilder.UpdateTrafficLightCoord(currentTrafficLight, endCoord, rotationDegree);
                }
                else if (currentTrafficSpawner != null)
                {
                    float radius = (currentTrafficSpawner.gameObject.transform.position - endCoord).magnitude;
                    roadBuilder.UpdateTrafficSpawnerRadius(currentTrafficSpawner, radius);

                    DrawRadius drawRadius = currentTrafficSpawner.gameObject.GetComponent<DrawRadius>();
                    drawRadius.radius = radius;
                }
            }
        }

        if (Input.GetKeyDown(KeyCode.DownArrow))
        {
            rotationDegree = (rotationDegree + 90) % 360;
        }
        else if (Input.GetKeyDown(KeyCode.UpArrow))
        {
            rotationDegree = (rotationDegree - 90) % 360;
        }
    }

    void OnDrawGizmosSelected()
    {
        foreach (ERRoad footpath in roadBuilder.GetFootpathObjects())
        {
            Vector3[] footpathSplineCenter = roadBuilder.GetFootpathSplinePoints(footpath);
            // Draw a yellow sphere at the transform's position
            Gizmos.color = Color.yellow;
            foreach (Vector3 pos in footpathSplineCenter)
            {
                Gizmos.DrawSphere(pos, 0.3f);
            }
        }
    }

    void OnMouseDown()
    {
        if (EventSystem.current.IsPointerOverGameObject())
        {
            return;
        }

        dragging = true;
        Vector3? startCoord = GetMouseWorldCoord();
        if (startCoord != null)
        {
            Vector3 coord = SnapToGrid((Vector3)startCoord);
            switch (elementPickerDropdown.selectedText.text)
            {
                case "Footpath":
                    currentFootpath = roadBuilder.CreateFootpath("Footpath", coord, false);
                    break;
                case "Crosswalk":
                    currentFootpath = roadBuilder.CreateFootpath("Crosswalk", coord, true);
                    break;
                case "Two-way Road":
                    ERRoadType twoWayRoadType = roadBuilder.roadNetwork.GetRoadTypeByName("2Lane-2Way");
                    currentRoad = roadBuilder.CreateRoad("2w2lnRoad", twoWayRoadType, coord, 6f);
                    break;
                case "Two-way Road (4 lanes)":
                    ERRoadType twoWayFourLanesRoadType = roadBuilder.roadNetwork.GetRoadTypeByName("4Lane-2Way");
                    currentRoad = roadBuilder.CreateRoad("2w4lnRoad", twoWayFourLanesRoadType, coord, 6f);
                    break;
                case "One-way Road (2 lanes)":
                    ERRoadType oneWayTwoLanesRoadType = roadBuilder.roadNetwork.GetRoadTypeByName("2Lane-1Way");
                    currentRoad = roadBuilder.CreateRoad("1w2lnRoad", oneWayTwoLanesRoadType, coord, 6f);
                    break;
                case "Traffic Light":
                    rotationDegree = 0;
                    currentTrafficLight = roadBuilder.CreateTrafficLight(coord);
                    break;
                case "Traffic Spawner":
                    currentTrafficSpawner = roadBuilder.CreateTrafficSpawner(coord);
                    DrawRadius drawRadius = currentTrafficSpawner.gameObject.AddComponent<DrawRadius>();
                    drawRadius.radius = currentTrafficSpawner.radius;
                    break;
            }
        }
    }

    void OnMouseUp()
    {
        dragging = false;

        if (currentRoad != null)
        {
            roadBuilder.ProcessNewRoad(currentRoad);
        }
        else if (currentFootpath != null)
        {
            roadBuilder.ProcessNewFootpath(currentFootpath);
        }

        currentRoad = null;
        currentFootpath = null;
        currentTrafficLight = null;
        currentTrafficSpawner = null;
    }

    private Vector3? GetMouseWorldCoord()
    {
        Ray ray = Camera.main.ScreenPointToRay(Input.mousePosition);
        if (coll.Raycast(ray, out RaycastHit hit, 1000.0f))
        {
            Vector3 point = ray.GetPoint(hit.distance);
            point.y = 0.0f;
            return point;
        }

        return null;
    }

    private Vector3 SnapToGrid(Vector3 pos)
    {
        float factor = 2f;
        return new Vector3(Mathf.Round(pos.x / factor) * factor,
                             pos.y,
                             Mathf.Round(pos.z / factor) * factor);
    }
}
