using UnityEngine;
using System.Collections;
using System;

[ExecuteAlways]
[RequireComponent(typeof(LineRenderer))]
public class DrawRadius : MonoBehaviour
{
    [Range(1, 50)] public int segments = 50;
    public float radius = 5f;
    [Range(0.1f, 5f)] public float width = 0.1f;
    public bool draw = true;

    [SerializeField] private LineRenderer line;

    private void Start()
    {
        if (!line) line = GetComponent<LineRenderer>();

        CreatePoints();
    }

    public void CreatePoints()
    {
        line.enabled = true;
        line.widthMultiplier = width;
        line.useWorldSpace = false;
        line.widthMultiplier = width;
        line.positionCount = segments + 1;

        float x;
        float y;

        var angle = 20f;
        var points = new Vector3[segments + 1];
        for (int i = 0; i < segments + 1; i++)
        {
            x = Mathf.Sin(Mathf.Deg2Rad * angle) * radius;
            y = Mathf.Cos(Mathf.Deg2Rad * angle) * radius;

            points[i] = new Vector3(x, 0f, y);

            angle += (380f / segments);
        }

        // it's way more efficient to do this in one go!
        line.SetPositions(points);
    }
    private float prevRadius;
    private int prevSegments;
    private float prevWidth;

    private void Update()
    {
        // Can't set up our line if the user hasn't connected it yet.
        if (!line) line = GetComponent<LineRenderer>();
        if (!line) return;

        if (!draw)
        {
            // instead simply disable the component
            line.enabled = false;
        }
        else
        {
            // Otherwise re-enable the component
            // This will simply re-use the previously created points
            line.enabled = true;

            if (radius != prevRadius || segments != prevSegments || width != prevWidth)
            {
                CreatePoints();

                // Cache our most recently used values.
                prevRadius = radius;
                prevSegments = segments;
                prevWidth = width;
            }
        }
    }
}